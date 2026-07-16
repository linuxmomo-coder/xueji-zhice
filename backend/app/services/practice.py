from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models import (
    Attempt,
    PracticeItem,
    PracticeSession,
    Question,
    QuestionResponseField,
    QuestionVersion,
    Student,
    WrongQuestion,
)
from app.repositories.questions import candidates
from app.services.grading import grade_answer


def _snapshot(question: Question, version: QuestionVersion) -> dict:
    return {
        "question_id": question.id,
        "question_code": question.question_code,
        "subject": question.subject,
        "grade": question.base_grade,
        "version_id": version.id,
        "version_no": version.version_no,
        "display_type": version.display_type,
        "stem": version.stem_content,
        "options": [
            {"key": item.option_key, "content": item.content, "sort_order": item.sort_order}
            for item in sorted(version.options, key=lambda option: option.sort_order)
        ],
        "difficulty": version.difficulty,
        "cognitive_level": version.cognitive_level,
        "estimated_seconds": version.estimated_seconds,
        "total_score": str(version.total_score),
    }


def create_session(
    db: Session,
    *,
    student: Student,
    subject: str,
    practice_type: str,
    question_count: int,
) -> PracticeSession:
    selected = candidates(
        db,
        subject=subject,
        grade=student.current_grade,
        limit=question_count,
    )
    if not selected:
        raise ApiError(
            404,
            "PRACTICE_002",
            f"当前学生{student.current_grade}年级的{subject}没有可用的已审核题目",
        )
    session = PracticeSession(
        family_id=student.family_id,
        student_id=student.id,
        practice_type=practice_type,
        subject=subject,
        total_count=len(selected),
    )
    db.add(session)
    db.flush()
    for index, (question, version) in enumerate(selected, start=1):
        db.add(
            PracticeItem(
                session_id=session.id,
                question_id=question.id,
                question_version_id=version.id,
                sequence_no=index,
                question_snapshot=_snapshot(question, version),
            )
        )
    db.commit()
    db.refresh(session)
    return session


def get_next_item(db: Session, session: PracticeSession) -> PracticeItem | None:
    return db.scalar(
        select(PracticeItem)
        .where(PracticeItem.session_id == session.id, PracticeItem.status == "pending")
        .order_by(PracticeItem.sequence_no)
    )


def submit_answer(
    db: Session,
    *,
    session: PracticeSession,
    item: PracticeItem,
    answer: dict,
    duration_seconds: int,
    hint_count: int,
) -> tuple[Attempt, WrongQuestion | None]:
    if session.status != "in_progress":
        raise ApiError(409, "PRACTICE_001", "练习已经结束")
    if item.session_id != session.id or item.status != "pending":
        raise ApiError(409, "PRACTICE_003", "该题已提交或不属于当前练习")

    version = db.scalar(
        select(QuestionVersion)
        .options(selectinload(QuestionVersion.response_fields).selectinload(QuestionResponseField.rules))
        .where(QuestionVersion.id == item.question_version_id)
    )
    if not version:
        raise ApiError(409, "BANK_002", "题目版本不存在")

    attempt_count = db.scalar(select(func.count(Attempt.id)).where(Attempt.practice_item_id == item.id)) or 0
    outcome = grade_answer(answer, version.response_fields, Decimal(version.total_score))
    attempt = Attempt(
        practice_item_id=item.id,
        student_id=session.student_id,
        attempt_no=attempt_count + 1,
        answer_raw=answer,
        answer_normalized=outcome.normalized,
        is_correct=outcome.correct,
        score=outcome.score,
        duration_seconds=duration_seconds,
        hint_count=hint_count,
        evaluation=outcome.details,
    )
    db.add(attempt)
    db.flush()
    item.status = "correct" if outcome.correct else "wrong"
    session.correct_count += 1 if outcome.correct else 0

    wrong: WrongQuestion | None = db.scalar(
        select(WrongQuestion).where(
            WrongQuestion.student_id == session.student_id,
            WrongQuestion.question_id == item.question_id,
        )
    )
    now = datetime.now(timezone.utc)
    if outcome.correct:
        if wrong and wrong.state in {"new", "learning", "retest_pending", "retest_failed"}:
            wrong.state = "original_passed"
            wrong.next_review_at = now + timedelta(days=3)
            wrong.latest_attempt_id = attempt.id
    else:
        if wrong:
            wrong.wrong_count += 1
            wrong.last_wrong_at = now
            wrong.state = "retest_failed" if session.practice_type == "retest" else "new"
            wrong.latest_attempt_id = attempt.id
            wrong.next_review_at = now + timedelta(days=1)
        else:
            wrong = WrongQuestion(
                student_id=session.student_id,
                question_id=item.question_id,
                wrong_count=1,
                state="new",
                latest_attempt_id=attempt.id,
                next_review_at=now + timedelta(days=1),
            )
            db.add(wrong)

    db.flush()
    if not get_next_item(db, session):
        session.status = "completed"
        session.finished_at = now
    db.commit()
    db.refresh(attempt)
    if wrong:
        db.refresh(wrong)
    return attempt, wrong
