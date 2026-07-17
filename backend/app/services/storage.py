from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.errors import ApiError

SUPPORTED_UPLOAD_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
}
PDF_DANGEROUS_MARKERS = (b"/JavaScript", b"/JS ", b"/Launch", b"/EmbeddedFile")


def detect_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def validate_upload_content(content: bytes, declared_content_type: str | None) -> str | None:
    if not declared_content_type:
        return None
    if declared_content_type not in SUPPORTED_UPLOAD_TYPES:
        raise ApiError(415, "FILE_001", "不支持的文件类型")
    detected = detect_content_type(content)
    if detected != declared_content_type:
        raise ApiError(415, "FILE_002", "文件真实格式与声明类型不一致")
    if detected == "application/pdf":
        sample = content[: 1024 * 1024]
        if any(marker in sample for marker in PDF_DANGEROUS_MARKERS):
            raise ApiError(415, "FILE_003", "PDF包含不允许的脚本、启动项或嵌入文件")
    return detected


@dataclass(frozen=True)
class StoredObject:
    provider: str
    object_key: str
    size_bytes: int


class PrivateStorage(Protocol):
    provider: str

    def save(self, object_key: str, content: bytes, *, content_type: str | None = None) -> StoredObject: ...

    def read(self, object_key: str) -> bytes: ...

    def delete(self, object_key: str) -> None: ...

    def temporary_url(self, object_key: str) -> str | None: ...


class LocalPrivateStorage:
    provider = "local"

    def __init__(self, root: str | Path = settings.file_storage_path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, object_key: str) -> Path:
        target = (self.root / object_key).resolve()
        if self.root != target and self.root not in target.parents:
            raise ValueError("非法对象路径")
        return target

    def save(self, object_key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        del content_type
        target = self._target(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StoredObject(provider=self.provider, object_key=object_key, size_bytes=len(content))

    def read(self, object_key: str) -> bytes:
        return self._target(object_key).read_bytes()

    def delete(self, object_key: str) -> None:
        target = self._target(object_key)
        if target.exists():
            target.unlink()

    def temporary_url(self, object_key: str) -> str | None:
        del object_key
        return None


class S3PrivateStorage:
    provider = "s3"

    def __init__(self) -> None:
        import boto3

        self.bucket = settings.storage_bucket or ""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
        )

    def save(self, object_key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        kwargs: dict[str, object] = {"Bucket": self.bucket, "Key": object_key, "Body": content}
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.put_object(**kwargs)
        return StoredObject(provider=self.provider, object_key=object_key, size_bytes=len(content))

    def read(self, object_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        return response["Body"].read()

    def delete(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def temporary_url(self, object_key: str) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=settings.storage_presign_seconds,
        )


def build_storage() -> PrivateStorage:
    if settings.storage_provider == "s3":
        return S3PrivateStorage()
    return LocalPrivateStorage()


class LazyStorage:
    """Delay backend construction until the first file operation."""

    def __init__(self) -> None:
        self._backend: PrivateStorage | None = None

    def _get(self) -> PrivateStorage:
        if self._backend is None:
            self._backend = build_storage()
        return self._backend

    @property
    def provider(self) -> str:
        return self._get().provider

    def save(self, object_key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        validate_upload_content(content, content_type)
        return self._get().save(object_key, content, content_type=content_type)

    def read(self, object_key: str) -> bytes:
        return self._get().read(object_key)

    def delete(self, object_key: str) -> None:
        self._get().delete(object_key)

    def temporary_url(self, object_key: str) -> str | None:
        return self._get().temporary_url(object_key)


storage = LazyStorage()
