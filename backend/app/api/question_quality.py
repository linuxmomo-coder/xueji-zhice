from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.questions import question_payload
from app.api.utils import success
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_accessible_student, get_current_user, require_roles
from app.models import (
    AnswerRegradeJob,
    Question,
    QuestionCorrectionReview,
    QuestionErrorReport,
    QuestionRelation,
    QuestionTaxonomyMapping,
    QuestionTaxonomyNode,
    QuestionVersion,
    RecommendationEvent,
    User,
    UserNotification,
)
from app.repositories.questions import get_published_version
from app.schemas_quality import (
    CorrectionReviewRequest,
    QuestionErrorReportCreate,
    QuestionRelationCreate,
    TaxonomyMappingCreate,
    TaxonomyNodeCreate,
)
from app.services.audit import add_audit_event
from app.services.question_quality import (
    RegradeQueueError,
    create_error_report,
    create_regrade_job,
    create_taxonomy_node,
    enqueue_regrade_job,
    recommend_questions,
    review_error_report,
)
from app.services.recovery import require_verified_email

router = APIRouter(tags=["题目质量与推荐"])


@router.post("/questions/{question_id}/error-reports", status_code=status.HTTP_201_CREATED)
def submit_question_error_report(
    question_id: str,
    payload: QuestionErrorReportCreate,
    request: Request,
    current_user: User = Depends(require_roles("parent", "student")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    question = db.get(Question, question_id)
    if not question:
        raise ApiError(404, "BANK_001", "题目不存在")
    version_id = payload.question_version_id or question.current_version_id
    version = db.get(QuestionVersion, version_id) if version_id else None
    if not version or version.question_id != question.id:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    student_id = payload.student_id
    if student_id:
        get_accessible_student(student_id, current_user, db)
    elif current_user.role == "student":
        students = list(
            db.scalars(
                select(__import__("app.models", fromlist=["Student"]).Student).where(
                    __import__("app.models", fromlist=["Student"]).Student.user_id == current_user.id
                )
            ).all()
        )
        student_id = students[0].id if students else None
    report = create_error_report(
        db,
        question=question,
        question_version=version,
        student_id=student_id,
        reported_by_user_id=current_user.id,
        report_type=payload.report_type,
        description=payload.description,
        suggested_answer=payload.suggested_answer,
        affects_scoring_claim=payload.affects_scoring_claim,
        submitted_context=payload.submitted_context,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_error_report.submit",
        resource_type="question_error_report",
        resource_id=report.id,
        request_id=request.state.request_id,
        after_data={
            "question_id": question.id,
            "question_version_id": version.id,
            "report_type": report.report_type,
            "affects_scoring_claim": report.affects_scoring_claim,
        },
    )
    db.commit()
    return success(
        request,
        {
            "id": report.id,
            "question_id": report.question_id,
            "question_version_id": report.question_version_id,
            "report_type": report.report_type,
            "status": report.status,
            "created_at": report.created_at,
        },
    )


@router.get("/admin/question-error-reports")
def list_error_reports(
    request: Request,
    status_filter: str | None = Query(default="submitted", alias="status"),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if status_filter:
        conditions.append(QuestionErrorReport.status == status_filter)
    rows = list(
        db.scalars(
            select(QuestionErrorReport)
            .where(*conditions)
            .order_by(QuestionErrorReport.created_at.desc())
            .limit(200)
        ).all()
    )
    data = []
    for report in rows:
        question = db.get(Question, report.question_id)
        data.append(
            {
                "id": report.id,
                "question_id": report.question_id,
                "question_code": question.question_code if question else None,
                "question_version_id": report.question_version_id,
                "student_id": report.student_id,
                "report_type": report.report_type,
                "description": report.description,
                "suggested_answer": report.suggested_answer,
                "affects_scoring_claim": report.affects_scoring_claim,
                "status": report.status,
                "submitted_context": report.submitted_context,
                "created_at": report.created_at,
            }
        )
    return success(request, data, total=len(data))


@router.post("/admin/question-error-reports/{report_id}/review")
def review_question_error_report(
    report_id: str,
    payload: CorrectionReviewRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    report = db.get(QuestionErrorReport, report_id)
    if not report:
        raise ApiError(404, "CORRECTION_007", "勘误记录不存在")
    review = review_error_report(
        db,
        report=report,
        reviewer_user_id=current_user.id,
        decision=payload.decision,
        findings=payload.findings,
        correction_payload=payload.correction_payload,
        affects_scoring=payload.affects_scoring,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_error_report.review",
        resource_type="question_correction_review",
        resource_id=review.id,
        request_id=request.state.request_id,
        after_data={
            "report_id": report.id,
            "decision": review.decision,
            "affects_scoring": review.affects_scoring,
            "corrected_version_id": review.corrected_version_id,
        },
    )
    db.commit()
    return success(
        request,
        {
            "id": review.id,
            "report_id": review.report_id,
            "decision": review.decision,
            "affects_scoring": review.affects_scoring,
            "corrected_version_id": review.corrected_version_id,
            "report_status": report.status,
        },
    )


@router.post("/admin/correction-reviews/{review_id}/regrade", status_code=status.HTTP_202_ACCEPTED)
def trigger_answer_regrade(
    review_id: str,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    review = db.get(QuestionCorrectionReview, review_id)
    if not review:
        raise ApiError(404, "REGRADE_004", "修正复核记录不存在")
    job = create_regrade_job(db, correction_review=review)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="answer_regrade.queue",
        resource_type="answer_regrade_job",
        resource_id=job.id,
        request_id=request.state.request_id,
        after_data={
            "old_version_id": job.old_version_id,
            "new_version_id": job.new_version_id,
        },
    )
    db.commit()
    if job.status == "queued":
        try:
            enqueue_regrade_job(job.id)
        except RegradeQueueError as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise ApiError(503, "REGRADE_005", "历史重判队列暂不可用") from exc
    return success(
        request,
        {
            "id": job.id,
            "status": job.status,
            "old_version_id": job.old_version_id,
            "new_version_id": job.new_version_id,
        },
    )


@router.get("/admin/regrade-jobs")
def list_regrade_jobs(
    request: Request,
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.scalars(
            select(AnswerRegradeJob)
            .order_by(AnswerRegradeJob.created_at.desc())
            .limit(200)
        ).all()
    )
    return success(
        request,
        [
            {
                "id": row.id,
                "question_id": row.question_id,
                "old_version_id": row.old_version_id,
                "new_version_id": row.new_version_id,
                "status": row.status,
                "total_attempts": row.total_attempts,
                "processed_attempts": row.processed_attempts,
                "changed_attempts": row.changed_attempts,
                "affected_students": row.affected_students,
                "error_message": row.error_message,
                "queued_at": row.queued_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ],
        total=len(rows),
    )


@router.post("/admin/taxonomy-nodes", status_code=status.HTTP_201_CREATED)
def add_taxonomy_node(
    payload: TaxonomyNodeCreate,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    node = create_taxonomy_node(db, **payload.model_dump())
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="taxonomy_node.create",
        resource_type="question_taxonomy_node",
        resource_id=node.id,
        request_id=request.state.request_id,
        after_data={"code": node.code, "node_type": node.node_type, "name": node.name},
    )
    db.commit()
    return success(
        request,
        {
            "id": node.id,
            "code": node.code,
            "node_type": node.node_type,
            "name": node.name,
            "subject": node.subject,
            "status": node.status,
        },
    )


@router.get("/admin/taxonomy-nodes")
def list_taxonomy_nodes(
    request: Request,
    subject: str | None = None,
    node_type: str | None = None,
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = [QuestionTaxonomyNode.status == "active"]
    if subject:
        conditions.append(QuestionTaxonomyNode.subject == subject)
    if node_type:
        conditions.append(QuestionTaxonomyNode.node_type == node_type)
    rows = list(
        db.scalars(
            select(QuestionTaxonomyNode)
            .where(*conditions)
            .order_by(QuestionTaxonomyNode.node_type, QuestionTaxonomyNode.name)
        ).all()
    )
    return success(
        request,
        [
            {
                "id": row.id,
                "code": row.code,
                "node_type": row.node_type,
                "name": row.name,
                "parent_id": row.parent_id,
                "subject": row.subject,
                "description": row.description,
            }
            for row in rows
        ],
        total=len(rows),
    )


@router.post("/admin/question-versions/{version_id}/taxonomy")
def map_question_taxonomy(
    version_id: str,
    payload: TaxonomyMappingCreate,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    version = db.get(QuestionVersion, version_id)
    node = db.get(QuestionTaxonomyNode, payload.taxonomy_node_id)
    if not version:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    if not node or node.status != "active":
        raise ApiError(404, "TAXONOMY_002", "题型节点不存在")
    existing = db.scalar(
        select(QuestionTaxonomyMapping).where(
            QuestionTaxonomyMapping.question_version_id == version.id,
            QuestionTaxonomyMapping.taxonomy_node_id == node.id,
        )
    )
    if existing:
        mapping = existing
        mapping.source = payload.source
        mapping.confidence = Decimal(str(payload.confidence)) if payload.confidence is not None else None
        mapping.review_status = payload.review_status
    else:
        mapping = QuestionTaxonomyMapping(
            question_version_id=version.id,
            taxonomy_node_id=node.id,
            source=payload.source,
            confidence=Decimal(str(payload.confidence)) if payload.confidence is not None else None,
            review_status=payload.review_status,
        )
        db.add(mapping)
    db.flush()
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_taxonomy.map",
        resource_type="question_taxonomy_mapping",
        resource_id=mapping.id,
        request_id=request.state.request_id,
        after_data={
            "question_version_id": version.id,
            "taxonomy_node_id": node.id,
            "review_status": mapping.review_status,
        },
    )
    db.commit()
    return success(
        request,
        {
            "id": mapping.id,
            "question_version_id": version.id,
            "taxonomy_node_id": node.id,
            "review_status": mapping.review_status,
        },
    )


@router.post("/admin/question-relations", status_code=status.HTTP_201_CREATED)
def add_question_relation(
    payload: QuestionRelationCreate,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    if payload.source_question_id == payload.target_question_id:
        raise ApiError(422, "RELATION_001", "题目不能与自身建立关系")
    if not db.get(Question, payload.source_question_id) or not db.get(Question, payload.target_question_id):
        raise ApiError(404, "BANK_001", "关联题目不存在")
    existing = db.scalar(
        select(QuestionRelation).where(
            QuestionRelation.source_question_id == payload.source_question_id,
            QuestionRelation.target_question_id == payload.target_question_id,
            QuestionRelation.relation_type == payload.relation_type,
        )
    )
    relation = existing or QuestionRelation(
        source_question_id=payload.source_question_id,
        target_question_id=payload.target_question_id,
        relation_type=payload.relation_type,
    )
    relation.strength = Decimal(str(payload.strength))
    relation.source = payload.source
    relation.review_status = payload.review_status
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return success(
        request,
        {
            "id": relation.id,
            "source_question_id": relation.source_question_id,
            "target_question_id": relation.target_question_id,
            "relation_type": relation.relation_type,
            "strength": str(relation.strength),
            "review_status": relation.review_status,
        },
    )


@router.get("/students/{student_id}/recommendations")
def get_recommendations(
    student_id: str,
    request: Request,
    limit: int = Query(default=10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    rows = recommend_questions(db, student=student, limit=limit)
    data = []
    for item in rows:
        reason = {
            "score": round(item["score"], 4),
            "matched_tags": item["matched_tags"],
            "relation_type": item["relation_type"],
        }
        event = RecommendationEvent(
            student_id=student.id,
            source_wrong_question_id=item["source_wrong_question_id"],
            recommended_question_id=item["question"].id,
            reason=reason,
            state="shown",
        )
        db.add(event)
        db.flush()
        data.append(
            {
                "event_id": event.id,
                "reason": reason,
                "question": question_payload(item["question"], item["version"], db),
            }
        )
    db.commit()
    return success(
        request,
        data,
        total=len(data),
        insufficient_data=not bool(data),
    )


@router.get("/notifications")
def list_notifications(
    request: Request,
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    conditions = [UserNotification.user_id == current_user.id]
    if unread_only:
        conditions.append(UserNotification.read_at.is_(None))
    rows = list(
        db.scalars(
            select(UserNotification)
            .where(*conditions)
            .order_by(UserNotification.created_at.desc())
            .limit(100)
        ).all()
    )
    return success(
        request,
        [
            {
                "id": row.id,
                "notification_type": row.notification_type,
                "title": row.title,
                "body": row.body,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "read_at": row.read_at,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        total=len(rows),
    )


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    notification = db.get(UserNotification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise ApiError(404, "NOTIFICATION_001", "通知不存在")
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    return success(request, {"id": notification.id, "read_at": notification.read_at})
