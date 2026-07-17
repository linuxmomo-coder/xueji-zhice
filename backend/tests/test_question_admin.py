from __future__ import annotations

import base64
from io import BytesIO

from openpyxl import Workbook


def _admin_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!", "role": "admin"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "题库采集"
    sheet.append([
        "question_code", "科目", "年级", "题型", "难度", "题干", "选项A", "选项B",
        "标准答案", "解析", "来源类型", "来源名称", "版权状态", "图片链接",
    ])
    sheet.append([
        "MATH-G8-IMPORT-0001", "数学", 8, "单选", 2, "1+1等于多少？", "1", "2",
        "B", "1+1=2。", "self_built", "项目原创", "owned", "",
    ])
    sheet.append([
        "MATH-G8-IMPORT-0002", "数学", 8, "填空", 2, "根据题图填写结果。", "", "",
        "3√3", "根式化简。", "licensed", "授权题库", "licensed", "https://source.invalid/question.png",
    ])
    sheet.append([
        "MATH-G8-IMPORT-BAD", "数学", 8, "填空", 2, "缺少答案的无效题", "", "",
        "", "", "self_built", "项目原创", "owned", "",
    ])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_question_import_requires_admin(client) -> None:
    response = client.post(
        "/api/v1/admin/question-imports/upload",
        files={"file": ("questions.xlsx", _workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 401


def test_question_import_review_publish_and_asset_migration(client) -> None:
    headers = _admin_headers(client)
    upload = client.post(
        "/api/v1/admin/question-imports/upload",
        headers=headers,
        files={"file": ("questions.xlsx", _workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 201, upload.text
    batch = upload.json()["data"]
    assert batch["total_rows"] == 3
    assert batch["valid_rows"] == 2
    assert batch["warning_rows"] == 1
    assert batch["failed_rows"] == 1
    assert batch["status"] == "validated_with_errors"

    details = client.get(f"/api/v1/admin/question-imports/{batch['id']}", headers=headers)
    assert details.status_code == 200
    failed_rows = [row for row in details.json()["data"]["rows"] if row["status"] == "failed"]
    assert len(failed_rows) == 1
    assert any("标准答案" in error for error in failed_rows[0]["errors"])

    committed = client.post(f"/api/v1/admin/question-imports/{batch['id']}/commit", headers=headers)
    assert committed.status_code == 200, committed.text
    assert committed.json()["data"]["committed_rows"] == 2

    pending = client.get("/api/v1/admin/question-versions?review_status=pending_review", headers=headers)
    assert pending.status_code == 200
    versions = {item["question_code"]: item for item in pending.json()["data"]}
    assert "MATH-G8-IMPORT-0001" in versions
    assert "MATH-G8-IMPORT-0002" in versions
    assert "MATH-G8-IMPORT-BAD" not in versions

    first = versions["MATH-G8-IMPORT-0001"]
    premature = client.post(
        f"/api/v1/admin/question-versions/{first['id']}/publish",
        headers=headers,
        json={"change_summary": "首次发布"},
    )
    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "PUBLISH_001"

    reviewed = client.post(
        f"/api/v1/admin/question-versions/{first['id']}/review",
        headers=headers,
        json={
            "decision": "approved",
            "review_type": "full",
            "comment": "内容、答案和版权均通过",
            "source_review_status": "approved",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    published = client.post(
        f"/api/v1/admin/question-versions/{first['id']}/publish",
        headers=headers,
        json={"change_summary": "审核通过后发布"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["data"]["publication_status"] == "published"

    image_version = versions["MATH-G8-IMPORT-0002"]
    reviewed_image = client.post(
        f"/api/v1/admin/question-versions/{image_version['id']}/review",
        headers=headers,
        json={
            "decision": "approved",
            "review_type": "full",
            "source_review_status": "approved",
        },
    )
    assert reviewed_image.status_code == 200, reviewed_image.text
    blocked_image = client.post(
        f"/api/v1/admin/question-versions/{image_version['id']}/publish",
        headers=headers,
        json={},
    )
    assert blocked_image.status_code == 409
    assert blocked_image.json()["error"]["code"] == "PUBLISH_004"

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZC8sAAAAASUVORK5CYII="
    )
    asset = client.post(
        "/api/v1/admin/question-assets",
        headers=headers,
        files={"file": ("question.png", png, "image/png")},
        data={"alt_text": "测试题图", "source_url": "https://source.invalid/question.png"},
    )
    assert asset.status_code == 201, asset.text
    asset_id = asset.json()["data"]["id"]
    linked = client.post(
        f"/api/v1/admin/question-versions/{image_version['id']}/assets",
        headers=headers,
        json={"asset_id": asset_id, "asset_role": "stem", "is_required": True},
    )
    assert linked.status_code == 200, linked.text
    published_image = client.post(
        f"/api/v1/admin/question-versions/{image_version['id']}/publish",
        headers=headers,
        json={"change_summary": "题图已迁移到自有存储"},
    )
    assert published_image.status_code == 200, published_image.text

    active = client.get("/api/v1/questions?grade=8&subject=数学&page_size=100", headers=headers)
    assert active.status_code == 200
    codes = {item["question_code"] for item in active.json()["data"]}
    assert "MATH-G8-IMPORT-0001" in codes
    assert "MATH-G8-IMPORT-0002" in codes
