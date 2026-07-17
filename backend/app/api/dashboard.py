from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import LearningDocument, PracticeSession, Question, QuestionVersion, Student, User, WrongQuestion
from app.repositories.users import get_primary_family_id

router = APIRouter(prefix="/dashboard", tags=["工作台"])


def _metric(label: str, value: int) -> dict[str, str | int]:
    return {"label": label, "value": value}


def _action(title: str, route: str, enabled: bool, reason: str | None = None) -> dict:
    return {"title": title, "route": route, "enabled": enabled, "reason": reason}


@router.get("")
def dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    family_id = get_primary_family_id(db, user.id)
    identity = {
        "user_id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "family_id": family_id,
    }
    active_question_count = db.scalar(
        select(func.count(Question.id))
        .join(QuestionVersion, Question.current_version_id == QuestionVersion.id)
        .where(
            Question.lifecycle_status == "active",
            QuestionVersion.review_status == "approved",
            QuestionVersion.publication_status == "published",
        )
    ) or 0

    if user.role == "admin":
        student_count = db.scalar(select(func.count(Student.id)).where(Student.deleted_at.is_(None))) or 0
        completed_practice_count = db.scalar(
            select(func.count(PracticeSession.id)).where(PracticeSession.status == "completed")
        ) or 0
        pending_documents = db.scalar(
            select(func.count(LearningDocument.id)).where(LearningDocument.status == "awaiting_confirmation")
        ) or 0
        metrics = [
            _metric("已发布题目", active_question_count),
            _metric("有效学生档案", student_count),
            _metric("已完成练习", completed_practice_count),
            _metric("待确认资料", pending_documents),
        ]
        actions = [_action("查看已发布题库", "/questions", True)]
        notices = [
            {"level": "insufficient_data", "text": "当前没有已发布题目。"}
            if active_question_count == 0
            else {"level": "fact", "text": f"当前共有 {active_question_count} 道已发布题目。"}
        ]
        if pending_documents:
            notices.append({"level": "fact", "text": f"当前有 {pending_documents} 份学习资料等待家长确认。"})
    else:
        student_conditions = [Student.deleted_at.is_(None)]
        if user.role == "student":
            student_conditions.append(Student.user_id == user.id)
        elif family_id:
            student_conditions.append(Student.family_id == family_id)
        else:
            student_conditions.append(Student.id.is_(None))
        students = list(db.scalars(select(Student).where(*student_conditions).order_by(Student.created_at)).all())
        student_ids = [item.id for item in students]
        grades = sorted({item.current_grade for item in students})
        completed_practice_count = 0
        wrong_count = 0
        pending_documents = 0
        available_question_count = 0
        if student_ids:
            completed_practice_count = db.scalar(
                select(func.count(PracticeSession.id)).where(
                    PracticeSession.student_id.in_(student_ids), PracticeSession.status == "completed"
                )
            ) or 0
            wrong_count = db.scalar(
                select(func.count(WrongQuestion.id)).where(
                    WrongQuestion.student_id.in_(student_ids), WrongQuestion.state != "mastered"
                )
            ) or 0
            pending_documents = db.scalar(
                select(func.count(LearningDocument.id)).where(
                    LearningDocument.student_id.in_(student_ids),
                    LearningDocument.status == "awaiting_confirmation",
                )
            ) or 0
            available_question_count = db.scalar(
                select(func.count(Question.id))
                .join(QuestionVersion, Question.current_version_id == QuestionVersion.id)
                .where(
                    Question.lifecycle_status == "active",
                    QuestionVersion.review_status == "approved",
                    QuestionVersion.publication_status == "published",
                    Question.base_grade.in_(grades),
                )
            ) or 0

        if user.role == "parent":
            metrics = [
                _metric("家庭学生档案", len(students)),
                _metric("已完成练习", completed_practice_count),
                _metric("待复习错题", wrong_count),
                _metric("待确认资料", pending_documents),
            ]
            actions = [
                _action("管理学生档案", "/students", True),
                _action(
                    "创建短练习",
                    "/practice",
                    bool(students) and available_question_count > 0,
                    "请先创建学生档案" if not students else "当前年级暂无已发布题目" if available_question_count == 0 else None,
                ),
                _action("上传成绩或评语", "/documents", bool(students), "请先创建学生档案" if not students else None),
            ]
        else:
            metrics = [
                _metric("可用练习题", available_question_count),
                _metric("已完成练习", completed_practice_count),
                _metric("待复习错题", wrong_count),
                _metric("待确认资料", pending_documents),
            ]
            actions = [
                _action(
                    "开始练习",
                    "/practice",
                    bool(students) and available_question_count > 0,
                    "账号尚未绑定学生档案" if not students else "当前年级暂无已发布题目" if available_question_count == 0 else None,
                ),
                _action("上传学习资料", "/documents", bool(students), "账号尚未绑定学生档案" if not students else None),
            ]
        notices = []
        if not students:
            notices.append({"level": "insufficient_data", "text": "当前账号尚未关联学生档案。"})
        if completed_practice_count == 0:
            notices.append({"level": "insufficient_data", "text": "暂无已完成练习，当前不能形成学习趋势判断。"})
        else:
            notices.append({"level": "fact", "text": f"已完成 {completed_practice_count} 次练习。"})
        if wrong_count:
            notices.append({"level": "fact", "text": f"有 {wrong_count} 道错题等待复习。"})
        if pending_documents:
            notices.append({"level": "fact", "text": f"有 {pending_documents} 份资料等待家长确认。"})

    return success(
        request,
        {
            "role": user.role,
            "identity": identity,
            "metrics": metrics,
            "actions": actions,
            "notices": notices,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": settings.app_env,
        },
    )
