from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import LearningDocument, PracticeSession, Question, Student, User, WrongQuestion
from app.repositories.users import get_primary_family_id

router = APIRouter(prefix="/dashboard", tags=["工作台"])


@router.get("")
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    family_id = get_primary_family_id(db, user.id)
    identity = {
        "user_id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "family_id": family_id,
    }
    if user.role == "admin":
        metrics = [
            {"label": "已发布题目", "value": db.scalar(select(func.count(Question.id)).where(Question.lifecycle_status == "active")) or 0},
            {"label": "学生档案", "value": db.scalar(select(func.count(Student.id)).where(Student.deleted_at.is_(None))) or 0},
            {"label": "练习会话", "value": db.scalar(select(func.count(PracticeSession.id))) or 0},
            {"label": "待确认资料", "value": db.scalar(select(func.count(LearningDocument.id)).where(LearningDocument.status == "awaiting_confirmation")) or 0},
        ]
        actions = [
            {"title": "审核题库版本", "route": "/questions", "enabled": True},
            {"title": "检查系统审计", "route": "/admin/audit", "enabled": False},
        ]
        notices = [{"level": "fact", "text": "管理员权限与学生/家长入口已分离。"}]
    else:
        student_conditions = [Student.deleted_at.is_(None)]
        if user.role == "student":
            student_conditions.append(Student.user_id == user.id)
        elif family_id:
            student_conditions.append(Student.family_id == family_id)
        students = list(db.scalars(select(Student).where(*student_conditions).order_by(Student.created_at)).all())
        student_ids = [item.id for item in students]
        practice_count = 0
        wrong_count = 0
        pending_documents = 0
        if student_ids:
            practice_count = db.scalar(select(func.count(PracticeSession.id)).where(PracticeSession.student_id.in_(student_ids))) or 0
            wrong_count = db.scalar(select(func.count(WrongQuestion.id)).where(WrongQuestion.student_id.in_(student_ids))) or 0
            pending_documents = db.scalar(
                select(func.count(LearningDocument.id)).where(
                    LearningDocument.student_id.in_(student_ids),
                    LearningDocument.status == "awaiting_confirmation",
                )
            ) or 0
        metrics = [
            {"label": "学生档案", "value": len(students)},
            {"label": "已完成练习", "value": practice_count},
            {"label": "待复习错题", "value": wrong_count},
            {"label": "待确认资料", "value": pending_documents},
        ]
        actions = [
            {"title": "创建短练习", "route": "/practice", "enabled": bool(students)},
            {"title": "上传成绩或评语", "route": "/documents", "enabled": bool(students)},
        ]
        notices = [
            {"level": "fact", "text": "当前身份由登录令牌确定，不再通过前端按钮切换。"},
            {"level": "insufficient_data", "text": "数据不足时系统不会强行生成确定性结论。"},
        ]
    return success(request, {"role": user.role, "identity": identity, "metrics": metrics, "actions": actions, "notices": notices})
