from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FamilyMember, User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower().strip(), User.deleted_at.is_(None)))


def get_primary_family_id(db: Session, user_id: str) -> str | None:
    membership = db.scalar(
        select(FamilyMember)
        .where(FamilyMember.user_id == user_id)
        .order_by(FamilyMember.is_primary_guardian.desc(), FamilyMember.created_at)
    )
    return membership.family_id if membership else None
