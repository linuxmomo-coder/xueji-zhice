from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import require_roles
from app.models import (
    Question,
    QuestionImportBatch,
    QuestionImportRow,
    QuestionReview,
    QuestionSource,
    QuestionVersion,
    User,
)
from app.schemas_question_admin import (
    QuestionAssetLinkRequest,
    QuestionImportBatchRead,
    QuestionImportRowRead,
    QuestionPublishRequest,
    QuestionReviewRequest,
)
from app.services.audit import add_audit_event
from app.services.question_import import commit_import_batch, validate_xlsx_import
from app.services.question_lifecycle import (
    link_asset,
    publish_question_version,
    review_question_version,
    save_question_asset,
    suspend_question,
)
from app.services.recovery import require_verified_email

router = APIRouter(prefix="/admin", tags=["题库管理"])
MAX_XLSX_BYTES = 20 * 1024 * 1024


@router.post("/question-imports/upload", status_code=status.HTTP_201_CREATED)
async def upload_question_import(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    file_name = Path(file.filename or "questions.xlsx").name
    if not file_name.lower().endswith(".xlsx"):
        raise ApiError(415, "IMPORT_004", "仅支持.xlsx题库文件")
    content = await file.read(MAX_XLSX_BYTES + 1)
    if len(content) > MAX_XLSX_BYTES:
        raise ApiError(413, "IMPORT_005", "题库文件不得超过20MB")
    batch = validate_xlsx_import(
        db,
        content=content,
        file_name=file_name,
        uploaded_by_user_id=current_user.id,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_import.validate",
        resource_type="question_import_batch",
        resource_id=batch.id,
        request_id=request.state.request_id,
        after_data={
            "file_name": batch.file_name,
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "failed_rows": batch.failed_rows,
        },
    )
    db.commit()
    return success(request, QuestionImportBatchRead.model_validate(batch).model_dump())


@router.get("/question-imports")
def list_question_imports(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.scalars(
            select(QuestionImportBatch)
            .order_by(QuestionImportBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    total = len(list(db.scalars(select(QuestionImportBatch.id)).all()))
    return success(
        request,
        [QuestionImportBatchRead.model_validate(row).model_dump() for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/question-imports/{batch_id}")
def get_question_import(
    batch_id: str,
    request: Request,
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    batch = db.get(QuestionImportBatch, batch_id)
    if not batch:
        raise ApiError(404, "IMPORT_006", "导入批次不存在")
    rows = list(
        db.scalars(
            select(QuestionImportRow)
            .where(QuestionImportRow.batch_id == batch.id)
            .order_by(QuestionImportRow.sheet_name, QuestionImportRow.row_number)
        ).all()
    )
    return success(
        request,
        {
            "batch": QuestionImportBatchRead.model_validate(batch).model_dump(),
            "rows": [QuestionImportRowRead.model_validate(row).model_dump() for row in rows],
        },
    )


@router.post("/question-imports/{batch_id}/commit")
def commit_question_import(
    batch_id: str,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    batch = db.get(QuestionImportBatch, batch_id)
    if not batch:
        raise ApiError(404, "IMPORT_006", "导入批次不存在")
    batch = commit_import_batch(db, batch, actor_user_id=current_user.id)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_import.commit",
        resource_type="question_import_batch",
        resource_id=batch.id,
        request_id=request.state.request_id,
        after_data={"committed_rows": batch.committed_rows},
    )
    db.commit()
    return success(request, QuestionImportBatchRead.model_validate(batch).model_dump())


@router.get("/question-versions")
def list_question_versions_for_review(
    request: Request,
    review_status: str | None = Query(default="pending_review"),
    publication_status: str | None = Query(default=None),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if review_status:
        conditions.append(QuestionVersion.review_status == review_status)
    if publication_status:
        conditions.append(QuestionVersion.publication_status == publication_status)
    versions = list(
        db.scalars(
            select(QuestionVersion)
            .where(*conditions)
            .order_by(QuestionVersion.created_at.desc())
            .limit(200)
        ).all()
    )
    data: list[dict] = []
    for version in versions:
        question = db.get(Question, version.question_id)
        source = db.get(QuestionSource, question.source_id) if question and question.source_id else None
        data.append(
            {
                "id": version.id,
                "question_id": version.question_id,
                "question_code": question.question_code if question else None,
                "subject": question.subject if question else None,
                "grade": question.base_grade if question else None,
                "version_no": version.version_no,
                "display_type": version.display_type,
                "stem_content": version.stem_content,
                "answer_summary": version.answer_summary,
                "review_status": version.review_status,
                "publication_status": version.publication_status,
                "source": {
                    "id": source.id,
                    "copyright_status": source.copyright_status,
                    "review_status": source.review_status,
                    "source_name": source.source_name,
                    "source_url": source.source_url,
                    "metadata": source.metadata_json,
                } if source else None,
            }
        )
    return success(request, data, total=len(data))


@router.post("/question-versions/{version_id}/review")
def review_version(
    version_id: str,
    payload: QuestionReviewRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    version = db.get(QuestionVersion, version_id)
    if not version:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    review = review_question_version(
        db,
        version=version,
        reviewer_user_id=current_user.id,
        decision=payload.decision,
        review_type=payload.review_type,
        comment=payload.comment,
        findings=payload.findings,
        source_review_status=payload.source_review_status,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question.review",
        resource_type="question_version",
        resource_id=version.id,
        request_id=request.state.request_id,
        after_data={"decision": review.decision, "review_type": review.review_type},
    )
    db.commit()
    return success(
        request,
        {
            "review_id": review.id,
            "question_version_id": review.question_version_id,
            "decision": review.decision,
            "review_type": review.review_type,
        },
    )


@router.post("/question-versions/{version_id}/publish")
def publish_version(
    version_id: str,
    payload: QuestionPublishRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    version = db.get(QuestionVersion, version_id)
    if not version:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    version = publish_question_version(db, version=version, change_summary=payload.change_summary)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question.publish",
        resource_type="question_version",
        resource_id=version.id,
        request_id=request.state.request_id,
        after_data={"publication_status": version.publication_status, "published_at": version.published_at.isoformat() if version.published_at else None},
    )
    db.commit()
    return success(
        request,
        {
            "id": version.id,
            "question_id": version.question_id,
            "review_status": version.review_status,
            "publication_status": version.publication_status,
            "published_at": version.published_at,
        },
    )


@router.post("/question-assets", status_code=status.HTTP_201_CREATED)
async def upload_question_asset(
    request: Request,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    asset = save_question_asset(
        db,
        content=content,
        declared_mime=file.content_type or "",
        original_name=Path(file.filename or "question-image").name,
        alt_text=alt_text,
        source_url=source_url,
        uploaded_by_user_id=current_user.id,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_asset.upload",
        resource_type="question_asset",
        resource_id=asset.id,
        request_id=request.state.request_id,
        after_data={"sha256": asset.sha256, "mime_type": asset.mime_type},
    )
    db.commit()
    return success(
        request,
        {
            "id": asset.id,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "sha256": asset.sha256,
            "alt_text": asset.alt_text,
        },
    )


@router.post("/question-versions/{version_id}/assets")
def link_question_asset(
    version_id: str,
    payload: QuestionAssetLinkRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    link = link_asset(
        db,
        question_version_id=version_id,
        asset_id=payload.asset_id,
        asset_role=payload.asset_role,
        option_key=payload.option_key,
        sort_order=payload.sort_order,
        is_required=payload.is_required,
        display_config=payload.display_config,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question_asset.link",
        resource_type="question_version_asset",
        resource_id=link.id,
        request_id=request.state.request_id,
        after_data={"question_version_id": version_id, "asset_id": payload.asset_id},
    )
    db.commit()
    return success(request, {"id": link.id, "question_version_id": version_id, "asset_id": payload.asset_id})


@router.post("/questions/{question_id}/suspend")
def suspend_published_question(
    question_id: str,
    request: Request,
    reason: str = Form(..., min_length=3, max_length=200),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    require_verified_email(db, current_user)
    question = db.get(Question, question_id)
    if not question:
        raise ApiError(404, "BANK_001", "题目不存在")
    question = suspend_question(db, question=question, reason=reason)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="question.suspend",
        resource_type="question",
        resource_id=question.id,
        request_id=request.state.request_id,
        after_data={"reason": reason},
    )
    db.commit()
    return success(request, {"id": question.id, "lifecycle_status": question.lifecycle_status, "reason": question.suspended_reason})
