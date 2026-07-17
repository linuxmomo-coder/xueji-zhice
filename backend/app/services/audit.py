from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditEvent


def add_audit_event(
    db: Session,
    *,
    actor_user_id: str | None,
    family_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str | None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            family_id=family_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            before_data=before_data,
            after_data=after_data,
        )
    )
