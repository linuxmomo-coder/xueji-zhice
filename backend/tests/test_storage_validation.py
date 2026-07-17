from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.services.storage import detect_content_type, validate_upload_content


def test_detect_supported_file_signatures() -> None:
    assert detect_content_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert detect_content_type(b"\xff\xd8\xffrest") == "image/jpeg"
    assert detect_content_type(b"RIFF\x00\x00\x00\x00WEBPrest") == "image/webp"
    assert detect_content_type(b"%PDF-1.7\nrest") == "application/pdf"
    assert detect_content_type(b"not-a-file") is None


def test_declared_mime_must_match_real_file() -> None:
    with pytest.raises(ApiError) as error:
        validate_upload_content(b"%PDF-1.7\nrest", "image/png")
    assert error.value.code == "FILE_002"


def test_pdf_with_active_content_is_rejected() -> None:
    with pytest.raises(ApiError) as error:
        validate_upload_content(
            b"%PDF-1.7\n1 0 obj << /JavaScript (alert) >> endobj",
            "application/pdf",
        )
    assert error.value.code == "FILE_003"


def test_valid_upload_signature_is_accepted() -> None:
    assert validate_upload_content(b"\x89PNG\r\n\x1a\nrest", "image/png") == "image/png"
