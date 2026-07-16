from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models import (
    AnswerRegradeJob,
    Attempt,
    FamilyMember,
    PracticeItem,
    PracticeSession,
    Question,
    QuestionAnswerRule,
    QuestionCorrectionReview,
    QuestionErrorReport,
    QuestionOption,
    QuestionRelation,
    QuestionResponseField,
    QuestionTaxonomyMapping,
    QuestionTaxonomyNode,
    QuestionVersion,
    RecommendationEvent,
    Student,
    StudentErrorProfile,
    UserNotification,
    WrongQuestion,
)
from app.repositories.questions import get_published_version
from app.services.grading import grade_answer

REGRADING_QUEUE = "xueji:regrade:jobs"
NODE_WEIGHTS = {
    "template": 6.0,
    "family": 4.0,
    "skill": 3.0,
    "error_pattern": 3.5,
    "representation": 1.5,
    "prerequisite": 1.0,
}


class RegradeQueueError(RuntimeError):
    pass


def _clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False)) if value is not None else None


def create_error_report(
    db: Session,
    *,
    question: Question,
    question_version: QuestionVersion,
    student_id: str | None,
    reported_by_user_id: str,
    report_type: str,
    description: str,
    suggested_answer: str | None,
    affects_scoring_claim: bool,
    submitted_context: dict | None,
) -> QuestionErrorReport:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = db.scalar(
        select(func.count(QuestionErrorReport.id)).where(
            QuestionErrorReport.reported_by_user_id == reported_by_user_id,
            QuestionErrorReport.created_at >= since,
        )
    ) or 0
    if recent_count >= 20:
        raise ApiError(429, "CORRECTION_001", "24小时内勘误提交次数过多，请稍后再试")
    duplicate = db.scalar(
        select(QuestionErrorReport).where(
            QuestionErrorReport.question_version_id == question_version.id,
            QuestionErrorReport.reported_by_user_id == reported_by_user_id,
            QuestionErrorReport.report_type == report_type,
            QuestionErrorReport.status.in_(["submitted", "admin_reviewing", "correction_draft"]),
        )
    )
    if duplicate:
        return duplicate
    report = QuestionErrorReport(
        question_id=question.id,
        question_version_id=question_version.id,
        student_id=student_id,
        reported_by_user_id=reported_by_user_id,
        report_type=report_type,
        description=description,
        suggested_answer=suggested_answer,
        affects_scoring_claim=affects_scoring_claim,
        status="submitted",
        submitted_context=submitted_context,
    )
    db.add(report)
    db.flush()
    return report


def _load_version_for_clone(db: Session, version_id: str) -> QuestionVersion:
    version = db.scalar(
        select(QuestionVersion)
        .options(
            selectinload(QuestionVersion.options),
            selectinload(QuestionVersion.response_fields).selectinload(QuestionResponseField.rules),
        )
        .where(QuestionVersion.id == version_id)
    )
    if not version:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    return version


def create_corrected_version(
    db: Session,
    *,
    source_version: QuestionVersion,
    correction_payload: dict[str, Any],
    reviewer_user_id: str,
    report_id: str,
) -> QuestionVersion:
    source_version = _load_version_for_clone(db, source_version.id)
    version_no = (
        db.scalar(
            select(func.max(QuestionVersion.version_no)).where(
                QuestionVersion.question_id == source_version.question_id
            )
        )
        or 0
    ) + 1
    allowed_content_keys = {
        "stem_content",
        "explanation_content",
        "difficulty",
        "cognitive_level",
        "estimated_seconds",
        "answer_summary",
        "common_errors",
    }
    unknown = set(correction_payload) - allowed_content_keys - {"accepted_values", "options"}
    if unknown:
        raise ApiError(422, "CORRECTION_002", f"不支持的修正字段：{', '.join(sorted(unknown))}")
    stem_content = correction_payload.get("stem_content", _clone_json(source_version.stem_content))
    explanation_content = correction_payload.get(
        "explanation_content", _clone_json(source_version.explanation_content)
    )
    checksum_payload = {
        "stem_content": stem_content,
        "explanation_content": explanation_content,
        "options": correction_payload.get(
            "options",
            {item.option_key: item.content for item in source_version.options},
        ),
        "accepted_values": correction_payload.get("accepted_values"),
        "report_id": report_id,
    }
    import hashlib

    checksum = hashlib.sha256(
        json.dumps(checksum_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    corrected = QuestionVersion(
        question_id=source_version.question_id,
        version_no=version_no,
        display_type=source_version.display_type,
        stem_content=stem_content,
        explanation_content=explanation_content,
        difficulty=int(correction_payload.get("difficulty", source_version.difficulty)),
        cognitive_level=correction_payload.get("cognitive_level", source_version.cognitive_level),
        estimated_seconds=int(
            correction_payload.get("estimated_seconds", source_version.estimated_seconds)
        ),
        scoring_mode=source_version.scoring_mode,
        total_score=source_version.total_score,
        common_errors=correction_payload.get(
            "common_errors", _clone_json(source_version.common_errors)
        ),
        answer_summary=correction_payload.get("answer_summary", source_version.answer_summary),
        content_checksum=checksum,
        review_status="pending_review",
        publication_status="unpublished",
        change_summary=f"由勘误报告 {report_id} 创建的修正版草稿",
        reviewed_by_user_id=None,
    )
    db.add(corrected)
    db.flush()

    option_override = correction_payload.get("options")
    if option_override is not None and not isinstance(option_override, dict):
        raise ApiError(422, "CORRECTION_003", "options必须为对象")
    source_options = {item.option_key: item for item in source_version.options}
    effective_options = option_override or {
        key: _clone_json(item.content) for key, item in source_options.items()
    }
    for sort_order, (option_key, option_content) in enumerate(effective_options.items(), start=1):
        content = (
            option_content
            if isinstance(option_content, dict)
            else {"blocks": [{"type": "text", "value": str(option_content)}]}
        )
        source_option = source_options.get(option_key)
        db.add(
            QuestionOption(
                question_version_id=corrected.id,
                option_key=option_key,
                content=_clone_json(content),
                sort_order=sort_order,
                is_fixed_position=source_option.is_fixed_position if source_option else False,
                metadata_json=_clone_json(source_option.metadata_json) if source_option else None,
            )
        )

    accepted_override = correction_payload.get("accepted_values")
    for field_index, source_field in enumerate(
        sorted(source_version.response_fields, key=lambda item: item.sort_order), start=1
    ):
        field = QuestionResponseField(
            question_version_id=corrected.id,
            field_key=source_field.field_key,
            field_type=source_field.field_type,
            prompt=source_field.prompt,
            sort_order=source_field.sort_order,
            required=source_field.required,
            score_weight=source_field.score_weight,
            input_config=_clone_json(source_field.input_config),
        )
        db.add(field)
        db.flush()
        for rule_index, source_rule in enumerate(source_field.rules, start=1):
            accepted_values = source_rule.accepted_values
            if accepted_override is not None and field_index == 1 and rule_index == 1:
                if not isinstance(accepted_override, list) or not accepted_override:
                    raise ApiError(422, "CORRECTION_004", "accepted_values必须为非空数组")
                accepted_values = accepted_override
            db.add(
                QuestionAnswerRule(
                    response_field_id=field.id,
                    rule_type=source_rule.rule_type,
                    accepted_values=_clone_json(accepted_values),
                    normalization_profile=source_rule.normalization_profile,
                    case_sensitive=source_rule.case_sensitive,
                    order_sensitive=source_rule.order_sensitive,
                    allow_fullwidth_equivalent=source_rule.allow_fullwidth_equivalent,
                    allow_fraction_decimal_equivalent=source_rule.allow_fraction_decimal_equivalent,
                    unit=source_rule.unit,
                    unit_required=source_rule.unit_required,
                    absolute_tolerance=source_rule.absolute_tolerance,
                    relative_tolerance=source_rule.relative_tolerance,
                    parser_profile=source_rule.parser_profile,
                    parse_failure_action=source_rule.parse_failure_action,
                    rule_version=source_rule.rule_version + 1,
                    metadata_json=_clone_json(source_rule.metadata_json),
                )
            )
    db.flush()
    return corrected


def review_error_report(
    db: Session,
    *,
    report: QuestionErrorReport,
    reviewer_user_id: str,
    decision: str,
    findings: dict | None,
    correction_payload: dict | None,
    affects_scoring: bool,
) -> QuestionCorrectionReview:
    if report.status not in {"submitted", "admin_reviewing", "uncertain"}:
        raise ApiError(409, "CORRECTION_005", "当前勘误状态不允许复核")
    corrected_version: QuestionVersion | None = None
    if decision == "valid":
        if not correction_payload:
            raise ApiError(422, "CORRECTION_006", "确认题目有误时必须提供修正内容")
        source_version = db.get(QuestionVersion, report.question_version_id)
        if not source_version:
            raise ApiError(404, "BANK_002", "原题版本不存在")
        corrected_version = create_corrected_version(
            db,
            source_version=source_version,
            correction_payload=correction_payload,
            reviewer_user_id=reviewer_user_id,
            report_id=report.id,
        )
        report.status = "correction_draft"
        if affects_scoring:
            question = db.get(Question, report.question_id)
            if question:
                question.lifecycle_status = "suspended"
                question.suspended_reason = "勘误确认影响判分，等待修正版发布与历史重判"
    elif decision == "invalid":
        report.status = "rejected"
    else:
        report.status = "uncertain"
    review = QuestionCorrectionReview(
        report_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=decision,
        findings=findings,
        correction_payload=correction_payload,
        affects_scoring=affects_scoring,
        corrected_version_id=corrected_version.id if corrected_version else None,
    )
    db.add(review)
    db.flush()
    return review


def create_regrade_job(
    db: Session,
    *,
    correction_review: QuestionCorrectionReview,
) -> AnswerRegradeJob:
    if not correction_review.affects_scoring or not correction_review.corrected_version_id:
        raise ApiError(409, "REGRADE_001", "该修正不需要历史重判")
    report = db.get(QuestionErrorReport, correction_review.report_id)
    corrected = db.get(QuestionVersion, correction_review.corrected_version_id)
    if not report or not corrected:
        raise ApiError(404, "REGRADE_002", "修正记录不完整")
    if corrected.publication_status != "published":
        raise ApiError(409, "REGRADE_003", "修正版尚未发布")
    existing = db.scalar(
        select(AnswerRegradeJob).where(
            AnswerRegradeJob.old_version_id == report.question_version_id,
            AnswerRegradeJob.new_version_id == corrected.id,
            AnswerRegradeJob.status.in_(["queued", "running", "completed"]),
        )
    )
    if existing:
        return existing
    job = AnswerRegradeJob(
        question_id=report.question_id,
        old_version_id=report.question_version_id,
        new_version_id=corrected.id,
        triggered_by_review_id=correction_review.id,
        status="queued",
        queued_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


def enqueue_regrade_job(job_id: str) -> None:
    try:
        Redis.from_url(settings.redis_url, decode_responses=True).rpush(REGRADING_QUEUE, job_id)
    except RedisError as exc:
        raise RegradeQueueError("历史重判队列暂不可用") from exc


def update_error_profiles(
    db: Session,
    *,
    student_id: str,
    question_version_id: str,
    question_id: str,
    is_correct: bool,
    attempted_at: datetime,
) -> None:
    mappings = list(
        db.scalars(
            select(QuestionTaxonomyMapping).where(
                QuestionTaxonomyMapping.question_version_id == question_version_id,
                QuestionTaxonomyMapping.review_status == "approved",
            )
        ).all()
    )
    for mapping in mappings:
        profile = db.scalar(
            select(StudentErrorProfile).where(
                StudentErrorProfile.student_id == student_id,
                StudentErrorProfile.taxonomy_node_id == mapping.taxonomy_node_id,
            )
        )
        if not profile:
            profile = StudentErrorProfile(
                student_id=student_id,
                taxonomy_node_id=mapping.taxonomy_node_id,
                evidence_summary={"question_ids": []},
            )
            db.add(profile)
            db.flush()
        profile.attempt_count += 1
        if is_correct:
            profile.consecutive_correct += 1
            profile.consecutive_incorrect = 0
        else:
            profile.incorrect_count += 1
            profile.consecutive_incorrect += 1
            profile.consecutive_correct = 0
        question_ids = list(profile.evidence_summary.get("question_ids", []))
        question_ids.append(question_id)
        profile.evidence_summary = {
            "question_ids": question_ids[-10:],
            "incorrect_rate": round(profile.incorrect_count / profile.attempt_count, 4),
        }
        if profile.attempt_count < 3 and profile.consecutive_incorrect < 2:
            profile.state = "insufficient_evidence"
            profile.next_review_at = attempted_at + timedelta(days=3)
        elif profile.consecutive_incorrect >= 2 or profile.incorrect_count / profile.attempt_count >= 0.5:
            profile.state = "weak"
            profile.next_review_at = attempted_at + timedelta(days=1)
        elif profile.consecutive_correct >= 3:
            profile.state = "stable"
            profile.next_review_at = attempted_at + timedelta(days=14)
        else:
            profile.state = "learning"
            profile.next_review_at = attempted_at + timedelta(days=3)
        profile.last_attempt_at = attempted_at


def _notify_regrade(db: Session, student: Student, question_id: str, changed: bool) -> None:
    members = list(
        db.scalars(
            select(FamilyMember).where(FamilyMember.family_id == student.family_id)
        ).all()
    )
    title = "题目修正后已重新判分"
    body = (
        "系统已根据修正版重新计算相关作答，部分判分结果发生变化，请查看练习和错题记录。"
        if changed
        else "系统已根据修正版复核相关作答，本次未发现判分结果变化。"
    )
    for member in members:
        db.add(
            UserNotification(
                user_id=member.user_id,
                family_id=student.family_id,
                notification_type="answer_regraded",
                title=title,
                body=body,
                resource_type="question",
                resource_id=question_id,
            )
        )


def process_regrade_job(job_id: str) -> str:
    with SessionLocal() as db:
        job = db.get(AnswerRegradeJob, job_id)
        if not job or job.status != "queued":
            return "ignored"
        version = db.scalar(
            select(QuestionVersion)
            .options(
                selectinload(QuestionVersion.response_fields).selectinload(
                    QuestionResponseField.rules
                )
            )
            .where(QuestionVersion.id == job.new_version_id)
        )
        if not version:
            job.status = "failed"
            job.error_message = "修正版不存在"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return "failed"
        rows = db.execute(
            select(Attempt, PracticeItem)
            .join(PracticeItem, Attempt.practice_item_id == PracticeItem.id)
            .where(
                PracticeItem.question_id == job.question_id,
                PracticeItem.question_version_id == job.old_version_id,
            )
            .order_by(Attempt.submitted_at)
        ).all()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.total_attempts = len(rows)
        db.commit()

    affected_students: dict[str, bool] = {}
    affected_sessions: set[str] = set()
    changed_count = 0
    with SessionLocal() as db:
        job = db.get(AnswerRegradeJob, job_id)
        version = _load_version_for_clone(db, job.new_version_id)
        rows = db.execute(
            select(Attempt, PracticeItem)
            .join(PracticeItem, Attempt.practice_item_id == PracticeItem.id)
            .where(
                PracticeItem.question_id == job.question_id,
                PracticeItem.question_version_id == job.old_version_id,
            )
            .order_by(Attempt.submitted_at)
        ).all()
        for attempt, item in rows:
            outcome = grade_answer(attempt.answer_raw, version.response_fields, Decimal(version.total_score))
            old_correct = attempt.is_correct
            old_score = str(attempt.score)
            changed = old_correct != outcome.correct or Decimal(attempt.score) != outcome.score
            if changed:
                changed_count += 1
            history = list((attempt.evaluation or {}).get("regrade_history", []))
            history.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "old_version_id": job.old_version_id,
                    "new_version_id": job.new_version_id,
                    "old_correct": old_correct,
                    "new_correct": outcome.correct,
                    "old_score": old_score,
                    "new_score": str(outcome.score),
                }
            )
            attempt.is_correct = outcome.correct
            attempt.score = outcome.score
            attempt.answer_normalized = outcome.normalized
            attempt.evaluation = {**outcome.details, "regrade_history": history[-10:]}
            item.status = "correct" if outcome.correct else "wrong"
            affected_students[attempt.student_id] = affected_students.get(attempt.student_id, False) or changed
            affected_sessions.add(item.session_id)
            job.processed_attempts += 1

        for session_id in affected_sessions:
            session = db.get(PracticeSession, session_id)
            if session:
                session.correct_count = db.scalar(
                    select(func.count(PracticeItem.id)).where(
                        PracticeItem.session_id == session_id,
                        PracticeItem.status == "correct",
                    )
                ) or 0

        for student_id, changed in affected_students.items():
            student = db.get(Student, student_id)
            if not student:
                continue
            latest = db.execute(
                select(Attempt, PracticeItem)
                .join(PracticeItem, Attempt.practice_item_id == PracticeItem.id)
                .where(
                    Attempt.student_id == student_id,
                    PracticeItem.question_id == job.question_id,
                )
                .order_by(Attempt.submitted_at.desc())
                .limit(1)
            ).first()
            wrong = db.scalar(
                select(WrongQuestion).where(
                    WrongQuestion.student_id == student_id,
                    WrongQuestion.question_id == job.question_id,
                )
            )
            if latest and latest[0].is_correct:
                if wrong:
                    wrong.state = "corrected_after_regrade"
                    wrong.next_review_at = datetime.now(timezone.utc) + timedelta(days=3)
                    wrong.latest_attempt_id = latest[0].id
            else:
                if not wrong:
                    wrong = WrongQuestion(
                        student_id=student_id,
                        question_id=job.question_id,
                        wrong_count=1,
                        state="new",
                        latest_attempt_id=latest[0].id if latest else None,
                        next_review_at=datetime.now(timezone.utc) + timedelta(days=1),
                    )
                    db.add(wrong)
                else:
                    wrong.state = "new"
                    wrong.next_review_at = datetime.now(timezone.utc) + timedelta(days=1)
            _notify_regrade(db, student, job.question_id, changed)

        job.changed_attempts = changed_count
        job.affected_students = len(affected_students)
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    return "completed"


def create_taxonomy_node(
    db: Session,
    *,
    code: str,
    node_type: str,
    name: str,
    parent_id: str | None,
    subject: str | None,
    description: str | None,
) -> QuestionTaxonomyNode:
    normalized_code = code.strip().upper()
    existing = db.scalar(select(QuestionTaxonomyNode).where(QuestionTaxonomyNode.code == normalized_code))
    if existing:
        return existing
    if parent_id and not db.get(QuestionTaxonomyNode, parent_id):
        raise ApiError(404, "TAXONOMY_001", "父级题型节点不存在")
    node = QuestionTaxonomyNode(
        code=normalized_code,
        node_type=node_type,
        name=name.strip(),
        parent_id=parent_id,
        subject=subject,
        description=description,
        status="active",
    )
    db.add(node)
    db.flush()
    return node


def recommend_questions(
    db: Session,
    *,
    student: Student,
    limit: int = 10,
) -> list[dict[str, Any]]:
    wrong_rows = list(
        db.scalars(
            select(WrongQuestion)
            .where(
                WrongQuestion.student_id == student.id,
                WrongQuestion.state.not_in(["mastered", "corrected_after_regrade"]),
            )
            .order_by(WrongQuestion.last_wrong_at.desc())
            .limit(30)
        ).all()
    )
    attempted_question_ids = set(
        db.scalars(
            select(PracticeItem.question_id)
            .join(Attempt, Attempt.practice_item_id == PracticeItem.id)
            .where(Attempt.student_id == student.id)
        ).all()
    )
    scores: dict[str, dict[str, Any]] = {}
    for wrong in wrong_rows:
        source_question = db.get(Question, wrong.question_id)
        if not source_question:
            continue
        source_version = get_published_version(db, source_question)
        if not source_version:
            continue
        mappings = list(
            db.scalars(
                select(QuestionTaxonomyMapping).where(
                    QuestionTaxonomyMapping.question_version_id == source_version.id,
                    QuestionTaxonomyMapping.review_status == "approved",
                )
            ).all()
        )
        node_ids = [mapping.taxonomy_node_id for mapping in mappings]
        nodes = {
            node.id: node
            for node in db.scalars(
                select(QuestionTaxonomyNode).where(QuestionTaxonomyNode.id.in_(node_ids))
            ).all()
        } if node_ids else {}
        candidate_version_ids = set(
            db.scalars(
                select(QuestionTaxonomyMapping.question_version_id).where(
                    QuestionTaxonomyMapping.taxonomy_node_id.in_(node_ids),
                    QuestionTaxonomyMapping.review_status == "approved",
                )
            ).all()
        ) if node_ids else set()
        relation_rows = list(
            db.scalars(
                select(QuestionRelation).where(
                    QuestionRelation.source_question_id == source_question.id,
                    QuestionRelation.review_status == "approved",
                )
            ).all()
        )
        relation_map = {row.target_question_id: row for row in relation_rows}
        candidate_questions = list(
            db.scalars(
                select(Question).where(
                    Question.lifecycle_status == "active",
                    Question.base_grade == student.current_grade,
                    Question.subject == source_question.subject,
                    Question.current_version_id.is_not(None),
                )
            ).all()
        )
        for candidate in candidate_questions:
            if candidate.id == source_question.id or candidate.id in attempted_question_ids:
                continue
            candidate_version = get_published_version(db, candidate)
            if not candidate_version:
                continue
            relation = relation_map.get(candidate.id)
            if candidate_version.id not in candidate_version_ids and not relation:
                continue
            candidate_mappings = list(
                db.scalars(
                    select(QuestionTaxonomyMapping).where(
                        QuestionTaxonomyMapping.question_version_id == candidate_version.id,
                        QuestionTaxonomyMapping.review_status == "approved",
                    )
                ).all()
            )
            matched_node_ids = node_ids and {
                mapping.taxonomy_node_id for mapping in candidate_mappings
            }.intersection(node_ids) or set()
            matched_nodes = [nodes[node_id] for node_id in matched_node_ids if node_id in nodes]
            score = sum(NODE_WEIGHTS.get(node.node_type, 1.0) for node in matched_nodes)
            if relation:
                score += float(relation.strength) * 8
                if relation.relation_type == "easier":
                    score += 2
            score += max(0, 2 - abs(candidate_version.difficulty - source_version.difficulty))
            current = scores.setdefault(
                candidate.id,
                {
                    "question": candidate,
                    "version": candidate_version,
                    "score": 0.0,
                    "source_wrong_question_id": wrong.id,
                    "matched_tags": [],
                    "relation_type": relation.relation_type if relation else None,
                },
            )
            if score > current["score"]:
                current["score"] = score
                current["source_wrong_question_id"] = wrong.id
                current["matched_tags"] = [
                    {"id": node.id, "type": node.node_type, "name": node.name}
                    for node in matched_nodes
                ]
                current["relation_type"] = relation.relation_type if relation else None
    return sorted(scores.values(), key=lambda item: (-item["score"], item["question"].question_code))[:limit]
