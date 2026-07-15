from __future__ import annotations

from typing import Any

from fastapi import Request


def success(request: Request, data: Any, **meta: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"data": data, "meta": {"request_id": request.state.request_id}}
    payload["meta"].update(meta)
    return payload
