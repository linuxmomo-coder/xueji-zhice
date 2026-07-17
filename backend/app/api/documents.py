from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_accessible_student, get_current_user, require_roles
from app.models import LearningDocument, OCRJob, User
from app.schemas import DocumentConfirmRequest, DocumentRead
from app.services.audit import add_audit_event
from app.services.legal import require_family_child_consent
from app.services.ocr import OCRQueueError, create_ocr_job, enqueue_job_id, retry_ocr_job
from app.services.recovery import require_verified_email
from app.services.storage import storage

router = APIRouter(prefix="/documents", tags=["学习资料"])
ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
ALLOWED_DOCUMENT_TYPES = {"score", "comment", "evaluation", "textbook_cover", "textbook_catalog", "progress"}


def _job_payload(job: OCRJob | None) -> dict | None:
    if not job:
        return None
    return {
        "id": job.id,
        "provider": job.provider,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "next_retry_at": job.next_retry_at,
    }


@router.get("")
def list_documents(
    request: Request,
    student_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    conditions = [LearningDocument.student_id == student.id]
    if status_filter:
        conditions.append(LearningDocument.status == status_filter)
    rows = list(
        db.scalars(
            select(LearningDocument)
            .where(*conditions)
            .order_by(LearningDocument.created_at.desc())
        ).all()
    )
    return success(
        request,
        [DocumentRead.model_validate(row).model_dump() for row in rows],
        total=len(rows),
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    student_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    student = get_accessible_student(student_id, current_user, db)
    require_family_child_consent(db, student.family_id)
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ApiError(422, "DOC_001", "不支持的资料类型")
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME:
        raise ApiError(415, "DOC_003", "仅支持 PNG、JPEG、WebP 或 PDF")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ApiError(413, "DOC_004", f"文件不得超过 {settings.max_upload_mb}MB")
    if not content:
        raise ApiError(422, "DOC_007", "上传文件不能为空")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(LearningDocument).where(
            LearningDocument.student_id == student.id,
            LearningDocument.file_sha256 == digest,
        )
    )
    if existing:
        latest_job = db.scalar(
            select(OCRJob)
            .where(OCRJob.document_id == existing.id)
            .order_by(OCRJob.created_at.desc())
        )
        return success(
            request,
            DocumentRead.model_validate(existing).model_dump(),
            duplicate=True,
            ocr_job=_job_payload(latest_job),
        )

    relative = Path(student.family_id) / student.id / f"{digest}{ALLOWED_MIME[mime_type]}"
    stored = storage.save(str(relative).replace("\\", "/"), content, content_type=mime_type)
    document = LearningDocument(
        family_id=student.family_id,
        student_id=student.id,
        uploaded_by_user_id=current_user.id,
        document_type=document_type,
        file_name=Path(file.filename or "upload").name,
        storage_provider=stored.provider,
        storage_key=stored.object_key,
        file_sha256=digest,
        mime_type=mime_type,
        status="uploaded",
        structured_data=None,
    )
    db.add(document)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "DOC_005", "重复文件") from exc

    job: OCRJob | None = None
    if settings.ocr_enabled:
        job = create_ocr_job(db, document)
    else:
        document.status = "awaiting_confirmation"
        document.structured_data = {
            "mode": "manual_entry",
            "notice": "当前环境未启用OCR，请家长依据原文件人工录入并确认结构化数据。",
        }
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="document.upload",
        resource_type="learning_document",
        resource_id=document.id,
        request_id=request.state.request_id,
        after_data={
            "document_type": document_type,
            "file_sha256": digest,
            "ocr_enabled": settings.ocr_enabled,
            "ocr_job_id": job.id if job else None,
        },
    )
    db.commit()

    queue_error: str | None = None
    if job:
        try:
            enqueue_job_id(job.id)
        except OCRQueueError as exc:
            queue_error = str(exc)
            job = db.get(OCRJob, job.id)
            document = db.get(LearningDocument, document.id)
            if job and document:
                job.status = "failed"
                job.error_code = "QUEUE_UNAVAILABLE"
                job.error_message = queue_error
                job.finished_at = datetime.now(timezone.utc)
                document.status = "ocr_failed"
                document.structured_data = {
                    "mode": "ocr_failed",
                    "notice": "自动识别队列暂不可用，请稍后重试或人工录入。",
                    "error_code": "QUEUE_UNAVAILABLE",
                }
                db.commit()
    db.refresh(document)
    return success(
        request,
        DocumentRead.model_validate(document).model_dump(),
        duplicate=False,
        ocr_job=_job_payload(job),
        queue_error=queue_error,
    )


@router.get("/{document_id}")
def get_document(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    get_accessible_student(document.student_id, current_user, db)
    latest_job = db.scalar(
        select(OCRJob)
        .where(OCRJob.document_id == document.id)
        .order_by(OCRJob.created_at.desc())
    )
    return success(
        request,
        DocumentRead.model_validate(document).model_dump(),
        ocr_job=_job_payload(latest_job),
    )


@router.get("/{document_id}/ocr")
def get_ocr_status(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    get_accessible_student(document.student_id, current_user, db)
    job = db.scalar(
        select(OCRJob)
        .where(OCRJob.document_id == document.id)
        .order_by(OCRJob.created_at.desc())
    )
    return success(
        request,
        {
            "document_id": document.id,
            "document_status": document.status,
            "job": _job_payload(job),
        },
    )


@router.post("/{document_id}/ocr/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_document_ocr(
    document_id: str,
    request: Request,
    current_user: User = Depends(require_roles("parent", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    student = get_accessible_student(document.student_id, current_user, db)
    require_family_child_consent(db, student.family_id)
    job = retry_ocr_job(db, document)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="document.ocr.retry",
        resource_type="ocr_job",
        resource_id=job.id,
        request_id=request.state.request_id,
        after_data={"document_id": document.id, "provider": job.provider},
    )
    db.commit()
    try:
        enqueue_job_id(job.id)
    except OCRQueueError as exc:
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        document.status = "ocr_failed"
        db.commit()
        raise ApiError(503, "OCR_003", "OCR队列暂不可用，请稍后重试") from exc
    return success(request, _job_payload(job))


@router.get("/{document_id}/file")
def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    get_accessible_student(document.student_id, current_user, db)
    try:
        content = storage.read(document.storage_key)
    except (FileNotFoundError, OSError, KeyError) as exc:
        raise ApiError(404, "DOC_008", "资料文件不存在") from exc
    safe_name = Path(document.file_name).name.replace('"', "")
    fallback_name = "document" + ALLOWED_MIME.get(document.mime_type, "")
    encoded_name = quote(safe_name, safe="")
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{fallback_name}"; filename*=UTF-8\'\'{encoded_name}',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{document_id}/confirm")
def confirm_document(
    document_id: str,
    payload: DocumentConfirmRequest,
    request: Request,
    current_user: User = Depends(require_roles("parent")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    student = get_accessible_student(document.student_id, current_user, db)
    require_family_child_consent(db, student.family_id)
    if document.status != "awaiting_confirmation":
        raise ApiError(409, "DOC_002", "当前资料状态不允许确认")
    if not payload.confirmed_data:
        raise ApiError(422, "DOC_009", "确认数据不能为空")
    before = {"status": document.status, "confirmed_data": document.confirmed_data}
    document.confirmed_data = payload.confirmed_data
    document.status = "confirmed"
    document.confirmed_by_user_id = current_user.id
    document.confirmed_at = datetime.now(timezone.utc)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="document.confirm",
        resource_type="learning_document",
        resource_id=document.id,
        request_id=request.state.request_id,
        before_data=before,
        after_data={"status": "confirmed", "confirmed_data": payload.confirmed_data},
    )
    db.commit()
    db.refresh(document)
    return success(request, DocumentRead.model_validate(document).model_dump())
