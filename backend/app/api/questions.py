from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import Question, QuestionVersion, User
from app.repositories.questions import get_published_version, list_active

router = APIRouter(prefix="/questions", tags=["题库"])


def question_payload(question: Question, version: QuestionVersion) -> dict:
    return {
        "id": question.id,
        "question_code": question.question_code,
        "subject": question.subject,
        "grade": question.base_grade,
        "display_type": version.display_type,
        "difficulty": version.difficulty,
        "cognitive_level": version.cognitive_level,
        "stem": version.stem_content,
        "options": [
            {
                "key": option.option_key,
                "content": option.content,
                "sort_order": option.sort_order,
            }
            for option in sorted(version.options, key=lambda item: item.sort_order)
        ],
        "estimated_seconds": version.estimated_seconds,
    }


@router.get("/subjects")
def list_available_subjects(
    request: Request,
    grade: int = Query(ge=1, le=12),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(
        select(Question.subject, func.count(Question.id))
        .join(QuestionVersion, Question.current_version_id == QuestionVersion.id)
        .where(
            Question.lifecycle_status == "active",
            Question.base_grade == grade,
            QuestionVersion.review_status == "approved",
            QuestionVersion.publication_status == "published",
        )
        .group_by(Question.subject)
        .order_by(Question.subject)
    ).all()
    return success(
        request,
        [{"subject": subject, "question_count": count} for subject, count in rows],
    )


@router.get("")
def list_questions_endpoint(
    request: Request,
    subject: str | None = None,
    grade: int | None = Query(default=None, ge=1, le=12),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows, total = list_active(db, subject, grade, page, page_size)
    data = []
    for question in rows:
        version = get_published_version(db, question)
        if version:
            data.append(question_payload(question, version))
    return success(request, data, page=page, page_size=page_size, total=total)
