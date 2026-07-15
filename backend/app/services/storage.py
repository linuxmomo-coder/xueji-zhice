from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class StoredObject:
    provider: str
    object_key: str
    size_bytes: int


class LocalPrivateStorage:
    provider = "local"

    def __init__(self, root: str | Path = settings.file_storage_path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, object_key: str, content: bytes) -> StoredObject:
        target = (self.root / object_key).resolve()
        if self.root not in target.parents:
            raise ValueError("非法对象路径")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StoredObject(provider=self.provider, object_key=object_key, size_bytes=len(content))


# 后续增加 MinIOStorage/COSStorage，但业务层只依赖相同 save/open/delete 接口。
storage = LocalPrivateStorage()
