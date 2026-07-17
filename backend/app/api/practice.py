from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.questions import question_payload
from app.api.utils import success
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_accessible_student, get_current_user
from app.models import PracticeItem, PracticeSession, Question, Student, User, WrongQuestion
from app.repositories.questions import get_published_version
from app.schemas import AnswerSubmitRequest, PracticeCreateRequest, PracticeRead, WrongQuestionDetail, WrongQuestionRead
from app.services.legal import require_family_child_consent
from app.services.practice import create_retest_session, create_session, get_next_item, submit_answer
from app.services.recovery import require_verified_email

router = APIRouter(tags=["练习与错题"])


def _session_for_user(db: Session, session_id: str, user: User) -> PracticeSession:
    session = db.get(PracticeSession, session_id)
    if not session:
        raise ApiError(404, "PRACTICE_004", "练习不存在")
    if user.role == "admin":
        return session
    student = db.get(Student, session.student_id)
    if user.role == "student" and student and student.user_id == user.id:
        return session
    from app.repositories.users import get_primary_family_id

    family_id = get_primary_family_id(db, user.id)
    if user.role == "parent" and family_id == session.family_id:
        return session
    raise ApiError(403, "FAMILY_001", "无权访问该练习")


@router.post("/practice-sessions", status_code=status.HTTP_201_CREATED)
def create_practice(
    payload: PracticeCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    student = get_accessible_student(payload.student_id, current_user, db)
    require_family_child_consent(db, student.family_id)
    if payload.practice_type == "retest":
        raise ApiError(422, "PRACTICE_007", "原题复测必须从错题记录发起")
    session = create_session(
        db,
        student=student,
        subject=payload.subject,
        practice_type=payload.practice_type,
        question_count=payload.question_count,
    )
    return success(request, PracticeRead.model_validate(session).model_dump())


@router.get("/practice-sessions/{session_id}")
def get_practice(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = _session_for_user(db, session_id, current_user)
    return success(request, PracticeRead.model_validate(session).model_dump())


@router.get("/practice-sessions/{session_id}/next")
def next_question(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    session = _session_for_user(db, session_id, current_user)
    require_family_child_consent(db, session.family_id)
    item = get_next_item(db, session)
    if not item:
        return success(request, None, completed=True)
    question = db.get(Question, item.question_id)
    if not question:
        raise ApiError(409, "BANK_002", "题目不存在")
    version = get_published_version(db, question)
    if not version or version.id != item.question_version_id:
        snapshot = item.question_snapshot
        payload = {
            "id": item.question_id,
            "question_code": snapshot["question_code"],
            "subject": snapshot["subject"],
            "grade": snapshot["grade"],
            "display_type": snapshot["display_type"],
            "difficulty": snapshot["difficulty"],
            "cognitive_level": snapshot["cognitive_level"],
            "stem": snapshot["stem"],
            "options": snapshot["options"],
            "assets": [],
            "estimated_seconds": snapshot["estimated_seconds"],
        }
    else:
        payload = question_payload(question, version, db)
    return success(
        request,
        {"id": item.id, "sequence_no": item.sequence_no, "status": item.status, "question": payload},
        completed=False,
    )


@router.post("/practice-sessions/{session_id}/answers")
def answer_question(
    session_id: str,
    payload: AnswerSubmitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    session = _session_for_user(db, session_id, current_user)
    require_family_child_consent(db, session.family_id)
    item = db.get(PracticeItem, payload.practice_item_id)
    if not item:
        raise ApiError(404, "PRACTICE_005", "练习题不存在")
    attempt, wrong = submit_answer(
        db,
        session=session,
        item=item,
        answer=payload.answer,
        duration_seconds=payload.duration_seconds,
        hint_count=payload.hint_count,
    )
    return success(
        request,
        {
            "attempt_id": attempt.id,
            "is_correct": attempt.is_correct,
            "score": str(attempt.score),
            "normalized_answer": attempt.answer_normalized,
            "feedback": (
                "答案格式或表达式需要人工复核"
                if attempt.evaluation.get("manual_review_required")
                else "回答正确"
                if attempt.is_correct
                else "答案不正确，已加入错题复习"
            ),
            "wrong_question_state": wrong.state if wrong else None,
        },
    )


@router.get("/students/{student_id}/wrong-questions")
def list_wrong_questions(
    student_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    rows = list(
        db.scalars(
            select(WrongQuestion)
            .where(WrongQuestion.student_id == student.id)
            .order_by(WrongQuestion.last_wrong_at.desc())
        ).all()
    )
    data: list[dict] = []
    for row in rows:
        question = db.get(Question, row.question_id)
        version = get_published_version(db, question) if question else None
        if not question or not version:
            continue
        data.append(
            WrongQuestionDetail(
                wrong_question=WrongQuestionRead.model_validate(row),
                question=question_payload(question, version, db),
            ).model_dump()
        )
    return success(request, data)


@router.post("/students/{student_id}/wrong-questions/{wrong_question_id}/retest", status_code=status.HTTP_201_CREATED)
def retest_wrong_question(
    student_id: str,
    wrong_question_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    student = get_accessible_student(student_id, current_user, db)
    require_family_child_consent(db, student.family_id)
    wrong = db.get(WrongQuestion, wrong_question_id)
    if not wrong or wrong.student_id != student.id:
        raise ApiError(404, "PRACTICE_008", "错题记录不存在")
    session = create_retest_session(db, student=student, wrong_question=wrong)
    return success(request, PracticeRead.model_validate(session).model_dump())
