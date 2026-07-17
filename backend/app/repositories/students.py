from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Student


def list_for_family(db: Session, family_id: str, page: int, page_size: int) -> tuple[list[Student], int]:
    filters = (Student.family_id == family_id, Student.deleted_at.is_(None))
    total = db.scalar(select(func.count(Student.id)).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Student)
            .where(*filters)
            .order_by(Student.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return rows, total


def get_for_family(db: Session, student_id: str, family_id: str) -> Student | None:
    return db.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.family_id == family_id,
            Student.deleted_at.is_(None),
        )
    )
