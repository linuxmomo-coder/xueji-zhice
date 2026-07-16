from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_str


class GuardianConsent(Base, TimestampMixin):
    __tablename__ = "guardian_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    guardian_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[str] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    terms_version: Mapped[str] = mapped_column(String(40))
    privacy_version: Mapped[str] = mapped_column(String(40))
    child_policy_version: Mapped[str] = mapped_column(String(40))
    consent_scope: Mapped[dict] = mapped_column(JSON, default=dict)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
