from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.models import (
    Question,
    QuestionAsset,
    QuestionReview,
    QuestionSource,
    QuestionVersion,
    QuestionVersionAsset,
)
from app.services.storage import storage

ALLOWED_IMAGE_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
PUBLISHABLE_COPYRIGHT = {"owned", "licensed", "public_domain"}


def _detect_image_mime(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_question_asset(
    db: Session,
    *,
    content: bytes,
    declared_mime: str,
    original_name: str,
    alt_text: str | None,
    source_url: str | None,
    uploaded_by_user_id: str,
) -> QuestionAsset:
    if not content:
        raise ApiError(422, "ASSET_001", "图片文件不能为空")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "ASSET_002", f"题图不得超过 {settings.max_upload_mb}MB")
    detected = _detect_image_mime(content)
    if not detected or detected not in ALLOWED_IMAGE_MIME:
        raise ApiError(415, "ASSET_003", "仅支持真实的PNG、JPEG或WebP图片")
    if declared_mime and declared_mime != detected:
        raise ApiError(415, "ASSET_004", "文件声明类型与实际图片格式不一致")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(QuestionAsset).where(QuestionAsset.sha256 == digest))
    if existing:
        return existing
    extension = ALLOWED_IMAGE_MIME[detected]
    object_key = f"question-assets/{digest[:2]}/{digest}{extension}"
    stored = storage.save(object_key, content, content_type=detected)
    asset = QuestionAsset(
        storage_provider=stored.provider,
        bucket=settings.storage_bucket or "local-private",
        object_key=stored.object_key,
        mime_type=detected,
        size_bytes=len(content),
        sha256=digest,
        alt_text=(alt_text or Path(original_name).stem)[:500],
        source_url=source_url,
        source_metadata={"uploaded_by_user_id": uploaded_by_user_id, "original_name": Path(original_name).name},
        status="active",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def link_asset(
    db: Session,
    *,
    question_version_id: str,
    asset_id: str,
    asset_role: str,
    option_key: str | None,
    sort_order: int,
    is_required: bool,
    display_config: dict | None,
) -> QuestionVersionAsset:
    version = db.get(QuestionVersion, question_version_id)
    asset = db.get(QuestionAsset, asset_id)
    if not version:
        raise ApiError(404, "BANK_002", "题目版本不存在")
    if not asset or asset.status != "active":
        raise ApiError(404, "ASSET_005", "题目图片资产不存在")
    if asset_role == "option" and not option_key:
        raise ApiError(422, "ASSET_006", "选项图片必须指定option_key")
    existing = db.scalar(
        select(QuestionVersionAsset).where(
            QuestionVersionAsset.question_version_id == question_version_id,
            QuestionVersionAsset.asset_id == asset_id,
            QuestionVersionAsset.asset_role == asset_role,
            QuestionVersionAsset.option_key == option_key,
        )
    )
    if existing:
        return existing
    link = QuestionVersionAsset(
        question_version_id=question_version_id,
        asset_id=asset_id,
        asset_role=asset_role,
        option_key=option_key,
        sort_order=sort_order,
        is_required=is_required,
        display_config=display_config,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def review_question_version(
    db: Session,
    *,
    version: QuestionVersion,
    reviewer_user_id: str,
    decision: str,
    review_type: str,
    comment: str | None,
    findings: dict | None,
    source_review_status: str | None,
) -> QuestionReview:
    if version.publication_status == "published":
        raise ApiError(409, "REVIEW_001", "已发布版本不能重新审核，请创建新版本")
    question = db.get(Question, version.question_id)
    source = db.get(QuestionSource, question.source_id) if question and question.source_id else None
    if source_review_status and source:
        source.review_status = source_review_status
    version.review_status = decision
    version.reviewed_by_user_id = reviewer_user_id
    version.reviewed_at = datetime.now(timezone.utc)
    review = QuestionReview(
        question_version_id=version.id,
        review_type=review_type,
        decision=decision,
        reviewer_user_id=reviewer_user_id,
        comment=comment,
        findings=findings,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def publish_question_version(
    db: Session,
    *,
    version: QuestionVersion,
    change_summary: str | None,
) -> QuestionVersion:
    if version.review_status != "approved":
        raise ApiError(409, "PUBLISH_001", "题目版本尚未审核通过")
    question = db.get(Question, version.question_id)
    if not question:
        raise ApiError(404, "BANK_001", "题目不存在")
    source = db.get(QuestionSource, question.source_id) if question.source_id else None
    if not source or source.review_status != "approved":
        raise ApiError(409, "PUBLISH_002", "题目来源和版权尚未审核通过")
    if source.copyright_status not in PUBLISHABLE_COPYRIGHT:
        raise ApiError(409, "PUBLISH_003", "当前版权状态禁止发布")
    external_images = (source.metadata_json or {}).get("external_image_urls") or []
    linked_assets = list(
        db.scalars(
            select(QuestionVersionAsset).where(
                QuestionVersionAsset.question_version_id == version.id
            )
        ).all()
    )
    if external_images and not linked_assets:
        raise ApiError(409, "PUBLISH_004", "外部题图尚未迁移到项目对象存储")
    now = datetime.now(timezone.utc)
    if question.current_version_id and question.current_version_id != version.id:
        old = db.get(QuestionVersion, question.current_version_id)
        if old and old.publication_status == "published":
            old.publication_status = "superseded"
    version.publication_status = "published"
    version.published_at = now
    if change_summary:
        version.change_summary = change_summary
    question.current_version_id = version.id
    question.lifecycle_status = "active"
    if question.first_published_at is None:
        question.first_published_at = now
    db.commit()
    db.refresh(version)
    return version


def suspend_question(db: Session, *, question: Question, reason: str) -> Question:
    question.lifecycle_status = "suspended"
    question.suspended_reason = reason[:200]
    db.commit()
    db.refresh(question)
    return question
