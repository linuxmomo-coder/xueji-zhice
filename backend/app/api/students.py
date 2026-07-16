from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.errors import ApiError
from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies import current_family_id, get_accessible_student, get_current_user, require_roles
from app.models import FamilyMember, Student, User
from app.repositories.students import list_for_family
from app.schemas import StudentAccountCreate, StudentCreate, StudentRead, UserRead
from app.services.audit import add_audit_event
from app.services.legal import require_active_child_consent

router = APIRouter(prefix="/students", tags=["学生档案"])


@router.get("")
def list_students(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    family_id: str = Depends(current_family_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows, total = list_for_family(db, family_id, page, page_size)
    if current_user.role == "student":
        rows = [row for row in rows if row.user_id == current_user.id]
        total = len(rows)
    return success(
        request,
        [StudentRead.model_validate(row).model_dump() for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    request: Request,
    family_id: str = Depends(current_family_id),
    current_user: User = Depends(require_roles("parent", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if current_user.role == "parent":
        require_active_child_consent(db, current_user.id, family_id)
    student = Student(
        family_id=family_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(student)
    db.flush()
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=family_id,
        action="student.create",
        resource_type="student",
        resource_id=student.id,
        request_id=request.state.request_id,
        after_data={"nickname": student.nickname, "current_grade": student.current_grade},
    )
    db.commit()
    db.refresh(student)
    return success(request, StudentRead.model_validate(student).model_dump())


@router.post("/{student_id}/account", status_code=status.HTTP_201_CREATED)
def create_student_account(
    student_id: str,
    payload: StudentAccountCreate,
    request: Request,
    current_user: User = Depends(require_roles("parent", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    if current_user.role == "parent":
        require_active_child_consent(db, current_user.id, student.family_id)
    if student.user_id:
        raise ApiError(409, "STUDENT_002", "该学生档案已经绑定登录账号")
    normalized_email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized_email)):
        raise ApiError(409, "AUTH_001", "该邮箱已经注册")

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role="student",
        display_name=payload.display_name or student.nickname,
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(
        FamilyMember(
            family_id=student.family_id,
            user_id=user.id,
            relation_type="student",
            is_primary_guardian=False,
            permissions={"practice": True, "upload_documents": True},
        )
    )
    student.user_id = user.id
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="student.account.create",
        resource_type="student",
        resource_id=student.id,
        request_id=request.state.request_id,
        after_data={"user_id": user.id, "email": normalized_email},
    )
    db.commit()
    db.refresh(user)
    return success(
        request,
        {
            "student": StudentRead.model_validate(student).model_dump(),
            "user": UserRead.model_validate(user).model_dump(),
        },
    )


@router.get("/{student_id}")
def get_student(
    request: Request,
    student: Student = Depends(get_accessible_student),
) -> dict:
    return success(request, StudentRead.model_validate(student).model_dump())
