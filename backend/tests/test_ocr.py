from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import LearningDocument, OCRJob, Student, User
from app.services.ocr import OCRResult, create_ocr_job, normalize_ocr_payload, process_ocr_job
from app.services.storage import storage


class FakeOCRProvider:
    name = "fake_paddle_http"

    def recognize(self, *, content: bytes, mime_type: str, file_name: str) -> OCRResult:
        assert content
        assert mime_type == "image/png"
        assert file_name == "score.png"
        return OCRResult(
            text="数学 98\n英语：92\n班主任评语 学习认真",
            pages=[
                {
                    "page": 1,
                    "blocks": [
                        {"text": "数学 98", "confidence": 0.99, "bbox": [0, 0, 10, 10]},
                        {"text": "英语：92", "confidence": 0.97, "bbox": [0, 11, 10, 20]},
                    ],
                }
            ],
            mean_confidence=0.98,
            provider=self.name,
        )


def test_normalize_paddle_payload() -> None:
    result = normalize_ocr_payload(
        {
            "pages": [
                {
                    "blocks": [
                        {"text": "数学 98", "confidence": 0.96, "bbox": [0, 0, 20, 10]},
                        {"rec_text": "英语 92", "rec_score": 0.94},
                    ]
                }
            ]
        },
        provider="paddle_http",
    )
    assert result.text == "数学 98\n英语 92"
    assert result.mean_confidence == 0.95
    assert result.pages[0]["blocks"][0]["bbox"] == [0, 0, 20, 10]


def test_process_ocr_job_stores_confidence_and_extracted_scores(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_provider", "paddle_http")
    content = b"\x89PNG\r\n\x1a\n" + b"test-ocr-image"
    digest = hashlib.sha256(content).hexdigest()
    object_key = f"ocr-tests/{digest}.png"
    storage.save(object_key, content, content_type="image/png")

    with SessionLocal() as db:
        student = db.scalar(select(Student).limit(1))
        uploader = db.scalar(select(User).where(User.role == "parent"))
        assert student and uploader
        document = LearningDocument(
            family_id=student.family_id,
            student_id=student.id,
            uploaded_by_user_id=uploader.id,
            document_type="score",
            file_name="score.png",
            storage_provider="local",
            storage_key=object_key,
            file_sha256=digest,
            mime_type="image/png",
            status="uploaded",
        )
        db.add(document)
        db.flush()
        job = create_ocr_job(db, document)
        job.queued_at = datetime.now(timezone.utc)
        db.commit()
        job_id = job.id
        document_id = document.id

    assert process_ocr_job(job_id, provider=FakeOCRProvider()) == "completed"

    with SessionLocal() as db:
        job = db.get(OCRJob, job_id)
        document = db.get(LearningDocument, document_id)
        assert job and document
        assert job.status == "completed"
        assert job.result_json["mean_confidence"] == 0.98
        assert document.status == "awaiting_confirmation"
        assert document.structured_data["provider"] == "fake_paddle_http"
        assert document.structured_data["extracted"]["scores"] == {"数学": 98.0, "英语": 92.0}
        assert document.structured_data["requires_guardian_confirmation"] is True
