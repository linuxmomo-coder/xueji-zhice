from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.utils import success

router = APIRouter(prefix="/demo", tags=["仅开发环境"])


@router.get("/accounts")
def demo_accounts(request: Request) -> dict:
    return success(
        request,
        {
            "warning": "仅用于本地开发，不得在生产环境启用",
            "accounts": [
                {"role": "parent", "email": "parent@example.com", "password": "Parent123!"},
                {"role": "student", "email": "student@example.com", "password": "Student123!"},
                {"role": "admin", "email": "admin@example.com", "password": "Admin123!"},
            ],
        },
    )
