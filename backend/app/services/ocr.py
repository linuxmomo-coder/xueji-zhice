from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models import LearningDocument, OCRJob
from app.services.storage import storage


class OCRProviderError(RuntimeError):
    pass


class OCRQueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRResult:
    text: str
    pages: list[dict[str, Any]]
    mean_confidence: float | None
    provider: str


class OCRProvider(Protocol):
    name: str

    def recognize(self, *, content: bytes, mime_type: str, file_name: str) -> OCRResult: ...


class PaddleHTTPOCRProvider:
    name = "paddle_http"

    def recognize(self, *, content: bytes, mime_type: str, file_name: str) -> OCRResult:
        if not settings.ocr_service_url:
            raise OCRProviderError("OCR_SERVICE_URL未配置")
        headers = {}
        if settings.ocr_service_token:
            headers["Authorization"] = f"Bearer {settings.ocr_service_token}"
        try:
            response = httpx.post(
                settings.ocr_service_url,
                files={"file": (file_name, content, mime_type)},
                headers=headers,
                timeout=settings.ocr_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OCRProviderError("PaddleOCR服务调用失败") from exc
        return normalize_ocr_payload(payload, provider=self.name)


def _text_node(node: Any, output: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        text = node.get("text") or node.get("rec_text") or node.get("transcription")
        if isinstance(text, str) and text.strip():
            confidence = node.get("confidence", node.get("score", node.get("rec_score")))
            try:
                confidence_value = float(confidence) if confidence is not None else None
            except (TypeError, ValueError):
                confidence_value = None
            output.append(
                {
                    "text": text.strip(),
                    "confidence": confidence_value,
                    "bbox": node.get("bbox") or node.get("box") or node.get("points"),
                }
            )
        for value in node.values():
            if isinstance(value, (dict, list)):
                _text_node(value, output)
    elif isinstance(node, list):
        for value in node:
            _text_node(value, output)


def normalize_ocr_payload(payload: Any, *, provider: str) -> OCRResult:
    if not isinstance(payload, (dict, list)):
        raise OCRProviderError("OCR服务返回格式无效")
    pages_source = payload.get("pages") if isinstance(payload, dict) else None
    pages: list[dict[str, Any]] = []
    if isinstance(pages_source, list):
        for index, page in enumerate(pages_source, start=1):
            blocks: list[dict[str, Any]] = []
            _text_node(page, blocks)
            pages.append({"page": index, "blocks": blocks})
    else:
        blocks = []
        _text_node(payload, blocks)
        pages.append({"page": 1, "blocks": blocks})
    all_blocks = [block for page in pages for block in page["blocks"]]
    if not all_blocks:
        raise OCRProviderError("OCR服务未返回可识别文本")
    confidences = [block["confidence"] for block in all_blocks if block.get("confidence") is not None]
    mean_confidence = sum(confidences) / len(confidences) if confidences else None
    text = "\n".join(block["text"] for block in all_blocks)
    return OCRResult(
        text=text,
        pages=pages,
        mean_confidence=round(mean_confidence, 6) if mean_confidence is not None else None,
        provider=provider,
    )


def extract_document_fields(document_type: str, text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if document_type == "score":
        subjects = "语文|数学|英语|物理|化学|生物|道德与法治|政治|历史|地理|体育"
        scores: dict[str, float] = {}
        for line in lines:
            for match in re.finditer(rf"({subjects})\s*[：:]?\s*(\d{{1,3}}(?:\.\d+)?)", line):
                value = float(match.group(2))
                if 0 <= value <= 150:
                    scores[match.group(1)] = value
        return {"scores": scores, "unparsed_lines": [line for line in lines if not any(subject in line for subject in scores)]}
    if document_type in {"comment", "evaluation"}:
        return {"text": "\n".join(lines)}
    if document_type in {"textbook_cover", "textbook_catalog"}:
        return {"lines": lines}
    return {"text": "\n".join(lines)}


def get_provider() -> OCRProvider:
    if settings.ocr_provider == "paddle_http":
        return PaddleHTTPOCRProvider()
    raise OCRProviderError("OCR提供方未启用")


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)


def enqueue_job_id(job_id: str) -> None:
    try:
        _redis().rpush(settings.ocr_queue_name, job_id)
    except RedisError as exc:
        raise OCRQueueError("OCR队列暂不可用") from exc


def create_ocr_job(db: Session, document: LearningDocument) -> OCRJob:
    now = datetime.now(timezone.utc)
    existing = db.scalar(
        select(OCRJob)
        .where(
            OCRJob.document_id == document.id,
            OCRJob.status.in_(["queued", "running"]),
        )
        .order_by(OCRJob.created_at.desc())
    )
    if existing:
        return existing
    job = OCRJob(
        document_id=document.id,
        provider=settings.ocr_provider,
        status="queued",
        attempts=0,
        max_attempts=settings.ocr_max_attempts,
        queued_at=now,
    )
    document.status = "ocr_queued"
    db.add(job)
    db.flush()
    return job


def retry_ocr_job(db: Session, document: LearningDocument) -> OCRJob:
    if not settings.ocr_enabled:
        raise ApiError(409, "OCR_001", "当前环境未启用OCR")
    latest = db.scalar(
        select(OCRJob)
        .where(OCRJob.document_id == document.id)
        .order_by(OCRJob.created_at.desc())
    )
    if latest and latest.status in {"queued", "running"}:
        raise ApiError(409, "OCR_002", "OCR任务正在处理中")
    return create_ocr_job(db, document)


def process_ocr_job(job_id: str, provider: OCRProvider | None = None) -> str:
    with SessionLocal() as db:
        job = db.get(OCRJob, job_id)
        if not job or job.status not in {"queued", "retrying"}:
            return "ignored"
        document = db.get(LearningDocument, job.document_id)
        if not document:
            job.status = "failed"
            job.error_code = "DOCUMENT_NOT_FOUND"
            job.error_message = "学习资料不存在"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return "failed"
        now = datetime.now(timezone.utc)
        job.status = "running"
        job.attempts += 1
        job.started_at = now
        document.status = "ocr_processing"
        db.commit()

    try:
        content = storage.read(document.storage_key)
        result = (provider or get_provider()).recognize(
            content=content,
            mime_type=document.mime_type,
            file_name=document.file_name,
        )
        extracted = extract_document_fields(document.document_type, result.text)
        with SessionLocal() as db:
            job = db.get(OCRJob, job_id)
            document = db.get(LearningDocument, job.document_id) if job else None
            if not job or not document:
                return "failed"
            job.status = "completed"
            job.result_json = {
                "provider": result.provider,
                "mean_confidence": result.mean_confidence,
                "pages": result.pages,
            }
            job.error_code = None
            job.error_message = None
            job.finished_at = datetime.now(timezone.utc)
            document.structured_data = {
                "mode": "ocr",
                "provider": result.provider,
                "mean_confidence": result.mean_confidence,
                "raw_text": result.text,
                "pages": result.pages,
                "extracted": extracted,
                "requires_guardian_confirmation": True,
            }
            document.status = "awaiting_confirmation"
            db.commit()
        return "completed"
    except (OCRProviderError, OSError, KeyError) as exc:
        with SessionLocal() as db:
            job = db.get(OCRJob, job_id)
            document = db.get(LearningDocument, job.document_id) if job else None
            if not job:
                return "failed"
            job.error_code = type(exc).__name__
            job.error_message = str(exc)[:1000]
            if job.attempts < job.max_attempts:
                job.status = "retrying"
                job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=min(60, 5 * job.attempts))
                if document:
                    document.status = "ocr_queued"
                db.commit()
                try:
                    enqueue_job_id(job.id)
                except OCRQueueError:
                    pass
                return "retrying"
            job.status = "failed"
            job.finished_at = datetime.now(timezone.utc)
            if document:
                document.status = "ocr_failed"
                document.structured_data = {
                    "mode": "ocr_failed",
                    "notice": "自动识别失败，请重试或由家长人工录入。",
                    "error_code": job.error_code,
                }
            db.commit()
        return "failed"
