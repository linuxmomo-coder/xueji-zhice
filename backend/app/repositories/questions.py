from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Question, QuestionVersion


def list_active(
    db: Session, subject: str | None, grade: int | None, page: int, page_size: int
) -> tuple[list[Question], int]:
    conditions = [Question.lifecycle_status == "active", Question.current_version_id.is_not(None)]
    if subject:
        conditions.append(Question.subject == subject)
    if grade:
        conditions.append(Question.base_grade == grade)
    total = db.scalar(select(func.count(Question.id)).where(*conditions)) or 0
    rows = list(
        db.scalars(
            select(Question)
            .where(*conditions)
            .order_by(Question.question_code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return rows, total


def get_published_version(db: Session, question: Question) -> QuestionVersion | None:
    if not question.current_version_id:
        return None
    return db.scalar(
        select(QuestionVersion)
        .options(selectinload(QuestionVersion.options), selectinload(QuestionVersion.response_fields))
        .where(
            QuestionVersion.id == question.current_version_id,
            QuestionVersion.publication_status == "published",
            QuestionVersion.review_status == "approved",
        )
    )


def candidates(
    db: Session,
    *,
    subject: str,
    grade: int,
    limit: int,
) -> list[tuple[Question, QuestionVersion]]:
    """Return published questions for the exact student grade and subject.

    Grade filtering is mandatory: a student must never receive questions from a
    different grade merely because the subject name matches.
    """
    questions = list(
        db.scalars(
            select(Question)
            .where(
                Question.lifecycle_status == "active",
                Question.subject == subject,
                Question.base_grade == grade,
                Question.current_version_id.is_not(None),
            )
            .order_by(Question.question_code)
            .limit(limit * 3)
        ).all()
    )
    output: list[tuple[Question, QuestionVersion]] = []
    for question in questions:
        version = get_published_version(db, question)
        if version:
            output.append((question, version))
        if len(output) >= limit:
            break
    return output
