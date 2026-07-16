from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Question, QuestionResponseField, QuestionVersion


def _published_conditions() -> list:
    return [
        Question.lifecycle_status == "active",
        Question.current_version_id.is_not(None),
        QuestionVersion.review_status == "approved",
        QuestionVersion.publication_status == "published",
    ]


def list_active(
    db: Session, subject: str | None, grade: int | None, page: int, page_size: int
) -> tuple[list[tuple[Question, QuestionVersion]], int]:
    conditions = _published_conditions()
    if subject:
        conditions.append(Question.subject == subject)
    if grade:
        conditions.append(Question.base_grade == grade)
    join_condition = Question.current_version_id == QuestionVersion.id
    total = db.scalar(select(func.count(Question.id)).join(QuestionVersion, join_condition).where(*conditions)) or 0
    rows = list(
        db.execute(
            select(Question, QuestionVersion)
            .join(QuestionVersion, join_condition)
            .options(
                selectinload(QuestionVersion.options),
                selectinload(QuestionVersion.response_fields).selectinload(QuestionResponseField.rules),
            )
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
        .options(
            selectinload(QuestionVersion.options),
            selectinload(QuestionVersion.response_fields).selectinload(QuestionResponseField.rules),
        )
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
    preferred_question_ids: list[str] | None = None,
) -> list[tuple[Question, QuestionVersion]]:
    preferred = preferred_question_ids or []
    statement = (
        select(Question, QuestionVersion)
        .join(QuestionVersion, Question.current_version_id == QuestionVersion.id)
        .options(
            selectinload(QuestionVersion.options),
            selectinload(QuestionVersion.response_fields).selectinload(QuestionResponseField.rules),
        )
        .where(*_published_conditions(), Question.subject == subject, Question.base_grade == grade)
    )
    if preferred:
        statement = statement.order_by(case((Question.id.in_(preferred), 0), else_=1), Question.question_code)
    else:
        statement = statement.order_by(Question.question_code)
    return list(db.execute(statement.limit(limit)).all())
