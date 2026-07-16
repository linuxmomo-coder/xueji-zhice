from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_accessible_student, get_current_user, require_roles
from app.models import LearningDocument, User
from app.schemas import DocumentConfirmRequest, DocumentRead
from app.services.audit import add_audit_event
from app.services.storage import storage

router = APIRouter(prefix="/documents", tags=["学习资料"])
ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
ALLOWED_DOCUMENT_TYPES = {
    "score",
    "comment",
    "evaluation",
    "textbook_cover",
    "textbook_catalog",
    "progress",
}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    student_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    student = get_accessible_student(student_id, current_user, db)
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ApiError(422, "DOC_001", "不支持的资料类型")
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME:
        raise ApiError(415, "DOC_003", "仅支持 PNG、JPEG、WebP 或 PDF")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ApiError(413, "DOC_004", f"文件不得超过 {settings.max_upload_mb}MB")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(LearningDocument).where(
            LearningDocument.student_id == student.id,
            LearningDocument.file_sha256 == digest,
        )
    )
    if existing:
        return success(
            request,
            DocumentRead.model_validate(existing).model_dump(),
            duplicate=True,
        )

    relative = Path(student.family_id) / student.id / f"{digest}{ALLOWED_MIME[mime_type]}"
    stored = storage.save(str(relative).replace("\\", "/"), content)
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
        status="awaiting_confirmation",
        structured_data={
            "mode": "manual_fallback",
            "notice": "OCR适配器尚未启用，请家长确认后录入",
        },
    )
    db.add(document)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "DOC_005", "重复文件") from exc
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=student.family_id,
        action="document.upload",
        resource_type="learning_document",
        resource_id=document.id,
        request_id=request.state.request_id,
        after_data={"document_type": document_type, "file_sha256": digest},
    )
    db.commit()
    db.refresh(document)
    return success(
        request,
        DocumentRead.model_validate(document).model_dump(),
        duplicate=False,
    )


@router.get("")
def list_documents(
    request: Request,
    student_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return success(
        request,
        [DocumentRead.model_validate(item).model_dump() for item in rows],
        page=page,
        page_size=page_size,
        total=len(rows),
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
    return success(request, DocumentRead.model_validate(document).model_dump())


@router.post("/{document_id}/confirm")
def confirm_document(
    document_id: str,
    payload: DocumentConfirmRequest,
    request: Request,
    current_user: User = Depends(require_roles("parent")),
    db: Session = Depends(get_db),
) -> dict:
    document = db.get(LearningDocument, document_id)
    if not document:
        raise ApiError(404, "DOC_006", "资料不存在")
    student = get_accessible_student(document.student_id, current_user, db)
    if document.status != "awaiting_confirmation":
        raise ApiError(409, "DOC_002", "当前资料状态不允许确认")
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
