from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_accessible_student, get_current_user, require_roles
from app.models import AIReport, User
from app.schemas_ai import AIReportCreate, AIReportRead
from app.services.ai_reports import (
    AIQueueError,
    create_report_job,
    enqueue_report_id,
    require_ai_consent,
)
from app.services.audit import add_audit_event
from app.services.recovery import require_verified_email

router = APIRouter(tags=["AI学习报告"])


def _report_for_user(db: Session, report_id: str, current_user: User) -> AIReport:
    report = db.get(AIReport, report_id)
    if not report:
        raise ApiError(404, "AI_005", "AI报告不存在")
    get_accessible_student(report.student_id, current_user, db)
    return report


@router.post("/ai-reports", status_code=status.HTTP_202_ACCEPTED)
def create_ai_report(
    payload: AIReportCreate,
    request: Request,
    current_user: User = Depends(require_roles("parent", "student")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    if not settings.ai_enabled:
        raise ApiError(409, "AI_004", "当前环境未启用AI报告")
    if current_user.role == "student" and payload.report_type != "student_report":
        raise ApiError(403, "AI_007", "学生账号只能生成学生版报告")
    student = get_accessible_student(payload.student_id, current_user, db)
    report = create_report_job(
        db,
        student=student,
        requested_by_user_id=current_user.id,
        report_type=payload.report_type,
    )
    created_new = report.status == "queued" and report.started_at is None and report.finished_at is None
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="ai_report.request",
        resource_type="ai_report",
        resource_id=report.id,
        request_id=request.state.request_id,
        after_data={
            "report_type": report.report_type,
            "prompt_version": report.prompt_version,
            "evidence_count": len(report.evidence_ids),
            "reused": not created_new,
        },
    )
    db.commit()
    if created_new:
        try:
            enqueue_report_id(report.id)
        except AIQueueError as exc:
            report.status = "failed"
            report.error_code = "QUEUE_UNAVAILABLE"
            report.error_message = str(exc)
            report.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise ApiError(503, "AI_008", "AI报告队列暂不可用，请稍后重试") from exc
    db.refresh(report)
    return success(
        request,
        AIReportRead.model_validate(report).model_dump(),
        reused=not created_new,
    )


@router.get("/students/{student_id}/ai-reports")
def list_ai_reports(
    student_id: str,
    request: Request,
    report_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    conditions = [AIReport.student_id == student.id]
    if report_type:
        conditions.append(AIReport.report_type == report_type)
    total = db.scalar(select(func.count(AIReport.id)).where(*conditions)) or 0
    rows = list(
        db.scalars(
            select(AIReport)
            .where(*conditions)
            .order_by(AIReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return success(
        request,
        [AIReportRead.model_validate(row).model_dump() for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/ai-reports/{report_id}")
def get_ai_report(
    report_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = _report_for_user(db, report_id, current_user)
    return success(request, AIReportRead.model_validate(report).model_dump())


@router.post("/ai-reports/{report_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_ai_report(
    report_id: str,
    request: Request,
    current_user: User = Depends(require_roles("parent", "student")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    if not settings.ai_enabled:
        raise ApiError(409, "AI_004", "当前环境未启用AI报告")
    report = _report_for_user(db, report_id, current_user)
    if current_user.role == "student" and report.report_type != "student_report":
        raise ApiError(403, "AI_007", "学生账号不能处理家长版报告")
    if report.status not in {"failed"}:
        raise ApiError(409, "AI_009", "只有失败报告可以重试")
    require_ai_consent(db, report.family_id)
    report.status = "queued"
    report.provider = "pending"
    report.model = "pending"
    report.error_code = None
    report.error_message = None
    report.queued_at = datetime.now(timezone.utc)
    report.started_at = None
    report.finished_at = None
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=report.family_id,
        action="ai_report.retry",
        resource_type="ai_report",
        resource_id=report.id,
        request_id=request.state.request_id,
    )
    db.commit()
    try:
        enqueue_report_id(report.id)
    except AIQueueError as exc:
        report.status = "failed"
        report.error_code = "QUEUE_UNAVAILABLE"
        report.error_message = str(exc)
        report.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise ApiError(503, "AI_008", "AI报告队列暂不可用，请稍后重试") from exc
    db.refresh(report)
    return success(request, AIReportRead.model_validate(report).model_dump())
