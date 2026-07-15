from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.utils import success
from app.db.session import get_db
from app.dependencies import current_family_id, get_accessible_student, get_current_user, require_roles
from app.models import Student, User
from app.repositories.students import list_for_family
from app.schemas import StudentCreate, StudentRead
from app.services.audit import add_audit_event

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


@router.get("/{student_id}")
def get_student(
    request: Request,
    student: Student = Depends(get_accessible_student),
) -> dict:
    return success(request, StudentRead.model_validate(student).model_dump())
