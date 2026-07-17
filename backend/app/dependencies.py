from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models import Student, User
from app.repositories.students import get_for_family
from app.repositories.users import get_primary_family_id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token, "access")
    except TokenError as exc:
        raise ApiError(401, "AUTH_001", str(exc)) from exc
    user = db.get(User, payload["sub"])
    if not user or user.status != "active" or user.deleted_at is not None:
        raise ApiError(401, "AUTH_001", "用户不存在或已停用")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ApiError(403, "AUTH_002", "当前身份无权执行此操作")
        return current_user

    return dependency


def current_family_id(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> str:
    family_id = get_primary_family_id(db, current_user.id)
    if not family_id:
        raise ApiError(403, "FAMILY_001", "当前账号未绑定家庭")
    return family_id


def get_accessible_student(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Student:
    if current_user.role == "admin":
        student = db.get(Student, student_id)
    elif current_user.role == "student":
        student = db.scalar(select(Student).where(Student.id == student_id, Student.user_id == current_user.id))
    else:
        family_id = get_primary_family_id(db, current_user.id)
        student = get_for_family(db, student_id, family_id) if family_id else None
    if not student or student.deleted_at is not None:
        raise ApiError(403, "FAMILY_001", "无权访问该学生数据")
    return student
