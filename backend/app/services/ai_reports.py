from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

import httpx
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models import (
    AIReport,
    LearningDocument,
    PracticeSession,
    Student,
    WrongQuestion,
)
from app.services.legal import get_any_active_family_consent

PROMPT_VERSION = "learning-report-v1"
ALLOWED_CONFIDENCE = {"fact", "high_confidence", "possible", "insufficient_data"}
REPORT_TYPES = {"student_report", "parent_report"}


class AIProviderError(RuntimeError):
    pass


class AIOutputError(RuntimeError):
    pass


class AIQueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    content: str
    provider: str
    model: str
    usage: dict[str, Any]


class AIProvider(Protocol):
    name: str
    model: str

    def generate(self, *, system_prompt: str, user_prompt: str) -> ProviderResult: ...


class OpenAICompatibleProvider:
    def __init__(self, *, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def generate(self, *, system_prompt: str, user_prompt: str) -> ProviderResult:
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.15,
                    "max_tokens": 2200,
                },
                timeout=settings.ai_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise AIProviderError("模型未返回有效内容")
            usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
            return ProviderResult(
                content=content,
                provider=self.name,
                model=str(payload.get("model") or self.model),
                usage=usage,
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIProviderError(f"{self.name}调用失败") from exc


def provider_from_name(name: str) -> AIProvider:
    if name == "bailian_openai":
        if not settings.dashscope_api_key:
            raise AIProviderError("百炼API Key未配置")
        return OpenAICompatibleProvider(
            name=name,
            base_url=settings.dashscope_base_url,
            api_key=settings.dashscope_api_key,
            model=settings.bailian_model,
        )
    if name == "hunyuan_openai":
        if not settings.hunyuan_api_key:
            raise AIProviderError("混元API Key未配置")
        return OpenAICompatibleProvider(
            name=name,
            base_url=settings.hunyuan_base_url,
            api_key=settings.hunyuan_api_key,
            model=settings.hunyuan_model,
        )
    raise AIProviderError("AI提供方未启用")


def _compact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[内容层级过深，已省略]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value[:1500]
    if isinstance(value, list):
        return [_compact_value(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, dict):
        return {
            str(key)[:100]: _compact_value(item, depth=depth + 1)
            for key, item in list(value.items())[:80]
        }
    return str(value)[:500]


def build_evidence_snapshot(
    db: Session,
    *,
    student: Student,
    days: int = 90,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sessions = list(
        db.scalars(
            select(PracticeSession)
            .where(
                PracticeSession.student_id == student.id,
                PracticeSession.status == "completed",
                PracticeSession.finished_at.is_not(None),
                PracticeSession.finished_at >= since,
            )
            .order_by(PracticeSession.finished_at.desc())
            .limit(200)
        ).all()
    )
    wrong_rows = list(
        db.scalars(
            select(WrongQuestion)
            .where(
                WrongQuestion.student_id == student.id,
                WrongQuestion.state != "mastered",
            )
            .order_by(WrongQuestion.last_wrong_at.desc())
            .limit(100)
        ).all()
    )
    documents = list(
        db.scalars(
            select(LearningDocument)
            .where(
                LearningDocument.student_id == student.id,
                LearningDocument.status == "confirmed",
                LearningDocument.confirmed_data.is_not(None),
            )
            .order_by(LearningDocument.confirmed_at.desc())
            .limit(50)
        ).all()
    )

    evidence: list[dict[str, Any]] = [
        {
            "id": f"student:{student.id}",
            "kind": "student_profile",
            "data": {
                "nickname": student.nickname,
                "grade": student.current_grade,
                "term": student.current_term,
            },
        }
    ]
    subject_metrics: dict[str, dict[str, int]] = {}
    total_questions = 0
    total_correct = 0
    for session in sessions:
        evidence.append(
            {
                "id": f"practice_session:{session.id}",
                "kind": "completed_practice",
                "data": {
                    "subject": session.subject,
                    "practice_type": session.practice_type,
                    "correct_count": session.correct_count,
                    "total_count": session.total_count,
                    "finished_at": session.finished_at,
                },
            }
        )
        metric = subject_metrics.setdefault(session.subject, {"sessions": 0, "correct": 0, "total": 0})
        metric["sessions"] += 1
        metric["correct"] += session.correct_count
        metric["total"] += session.total_count
        total_correct += session.correct_count
        total_questions += session.total_count

    for wrong in wrong_rows:
        evidence.append(
            {
                "id": f"wrong_question:{wrong.id}",
                "kind": "wrong_question_state",
                "data": {
                    "question_id": wrong.question_id,
                    "wrong_count": wrong.wrong_count,
                    "state": wrong.state,
                    "last_wrong_at": wrong.last_wrong_at,
                    "next_review_at": wrong.next_review_at,
                },
            }
        )

    for document in documents:
        evidence.append(
            {
                "id": f"document:{document.id}",
                "kind": "guardian_confirmed_document",
                "data": {
                    "document_type": document.document_type,
                    "confirmed_at": document.confirmed_at,
                    "confirmed_data": document.confirmed_data,
                },
            }
        )

    metrics = {
        "data_window_days": days,
        "completed_practice_count": len(sessions),
        "total_questions": total_questions,
        "total_correct": total_correct,
        "accuracy": round(total_correct / total_questions, 4) if total_questions else None,
        "active_wrong_question_count": len(wrong_rows),
        "confirmed_document_count": len(documents),
        "subject_metrics": {
            subject: {
                **values,
                "accuracy": round(values["correct"] / values["total"], 4) if values["total"] else None,
            }
            for subject, values in subject_metrics.items()
        },
    }
    compact = {
        "student": {
            "id": student.id,
            "nickname": student.nickname,
            "grade": student.current_grade,
            "term": student.current_term,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_window_days": days,
        "evidence": _compact_value(evidence),
    }
    encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > settings.ai_max_input_chars:
        compact["evidence"] = compact["evidence"][:100]
        compact["truncated"] = True
        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > settings.ai_max_input_chars:
            raise ApiError(413, "AI_006", "可用证据过多，请缩小报告时间范围")
    evidence_ids = [item["id"] for item in compact["evidence"]]
    return compact, metrics, evidence_ids


def require_ai_consent(db: Session, family_id: str) -> None:
    consent = get_any_active_family_consent(db, family_id)
    if not consent or not consent.consent_scope.get("automated_analysis"):
        raise ApiError(403, "AI_003", "监护人尚未授权自动学习分析")


def create_report_job(
    db: Session,
    *,
    student: Student,
    requested_by_user_id: str,
    report_type: str,
) -> AIReport:
    if report_type not in REPORT_TYPES:
        raise ApiError(422, "AI_001", "不支持的报告类型")
    if not settings.ai_enabled:
        raise ApiError(409, "AI_004", "当前环境未启用AI报告")
    require_ai_consent(db, student.family_id)
    snapshot, metrics, evidence_ids = build_evidence_snapshot(db, student=student)
    if metrics["completed_practice_count"] == 0 and metrics["confirmed_document_count"] == 0:
        raise ApiError(422, "AI_002", "数据不足：至少需要一次已完成练习或一份家长已确认资料")
    key_payload = {
        "student_id": student.id,
        "report_type": report_type,
        "prompt_version": settings.ai_prompt_version,
        "snapshot": snapshot,
    }
    generation_key = hashlib.sha256(
        json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    existing = db.scalar(select(AIReport).where(AIReport.generation_key == generation_key))
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    report = AIReport(
        family_id=student.family_id,
        student_id=student.id,
        requested_by_user_id=requested_by_user_id,
        report_type=report_type,
        status="queued",
        provider="pending",
        model="pending",
        prompt_version=settings.ai_prompt_version,
        generation_key=generation_key,
        metrics=metrics,
        evidence_snapshot=snapshot,
        output_json={},
        evidence_ids=evidence_ids,
        usage_json={},
        queued_at=now,
    )
    db.add(report)
    db.flush()
    return report


def _system_prompt(report_type: str) -> str:
    audience = "学生本人" if report_type == "student_report" else "学生家长"
    return f"""你是学迹智评的学习分析助手，报告对象是{audience}。
只能依据用户消息中的JSON证据生成报告，禁止补充常识性猜测、虚构成绩、虚构趋势或推断家庭背景。
所有事实、优势、改进点和行动建议都必须引用允许的evidence_id。
证据不足时必须使用confidence=insufficient_data并在limitations中明确说明。
不得进行医学、心理诊断，不得给学生贴负面标签，不得与其他学生比较。
输出只能是一个JSON对象，不得使用Markdown代码块或额外说明。
JSON结构必须为：
{{
  "summary": "字符串",
  "evidence_overview": [{{"statement":"字符串","confidence":"fact|high_confidence|possible|insufficient_data","evidence_ids":["证据ID"]}}],
  "strengths": [{{"statement":"字符串","confidence":"fact|high_confidence|possible|insufficient_data","evidence_ids":["证据ID"]}}],
  "improvements": [{{"statement":"字符串","confidence":"fact|high_confidence|possible|insufficient_data","evidence_ids":["证据ID"]}}],
  "actions": [{{"title":"字符串","reason":"字符串","priority":"high|medium|low","evidence_ids":["证据ID"]}}],
  "limitations": ["字符串"]
}}
每个数组最多5项，语言简洁、克制、可执行。"""


def _user_prompt(report: AIReport) -> str:
    return json.dumps(
        {
            "report_type": report.report_type,
            "metrics": report.metrics,
            "allowed_evidence_ids": report.evidence_ids,
            "evidence_snapshot": report.evidence_snapshot,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AIOutputError("模型输出不是JSON对象")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIOutputError("模型输出JSON无法解析") from exc
    if not isinstance(payload, dict):
        raise AIOutputError("模型输出必须为JSON对象")
    return payload


def validate_report_output(payload: dict[str, Any], allowed_evidence_ids: list[str]) -> dict[str, Any]:
    allowed = set(allowed_evidence_ids)
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise AIOutputError("报告缺少summary")
    normalized: dict[str, Any] = {"summary": summary.strip()[:1500]}
    for section in ("evidence_overview", "strengths", "improvements"):
        items = payload.get(section)
        if not isinstance(items, list):
            raise AIOutputError(f"报告缺少{section}数组")
        checked: list[dict[str, Any]] = []
        for item in items[:5]:
            if not isinstance(item, dict):
                raise AIOutputError(f"{section}项目格式无效")
            statement = item.get("statement")
            confidence = item.get("confidence")
            evidence_ids = item.get("evidence_ids")
            if not isinstance(statement, str) or not statement.strip():
                raise AIOutputError(f"{section}项目缺少statement")
            if confidence not in ALLOWED_CONFIDENCE:
                raise AIOutputError(f"{section}项目confidence无效")
            if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
                raise AIOutputError(f"{section}项目evidence_ids无效")
            unknown = set(evidence_ids) - allowed
            if unknown:
                raise AIOutputError(f"报告引用未知证据：{', '.join(sorted(unknown))}")
            if confidence != "insufficient_data" and not evidence_ids:
                raise AIOutputError(f"{section}中的确定性判断必须引用证据")
            checked.append(
                {
                    "statement": statement.strip()[:1000],
                    "confidence": confidence,
                    "evidence_ids": list(dict.fromkeys(evidence_ids))[:10],
                }
            )
        normalized[section] = checked

    actions = payload.get("actions")
    if not isinstance(actions, list):
        raise AIOutputError("报告缺少actions数组")
    checked_actions: list[dict[str, Any]] = []
    for item in actions[:5]:
        if not isinstance(item, dict):
            raise AIOutputError("actions项目格式无效")
        title = item.get("title")
        reason = item.get("reason")
        priority = item.get("priority")
        evidence_ids = item.get("evidence_ids")
        if not isinstance(title, str) or not title.strip() or not isinstance(reason, str) or not reason.strip():
            raise AIOutputError("actions项目缺少title或reason")
        if priority not in {"high", "medium", "low"}:
            raise AIOutputError("actions项目priority无效")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise AIOutputError("行动建议必须引用证据")
        if not all(isinstance(value, str) for value in evidence_ids) or set(evidence_ids) - allowed:
            raise AIOutputError("行动建议引用了未知证据")
        checked_actions.append(
            {
                "title": title.strip()[:300],
                "reason": reason.strip()[:1000],
                "priority": priority,
                "evidence_ids": list(dict.fromkeys(evidence_ids))[:10],
            }
        )
    normalized["actions"] = checked_actions

    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(value, str) for value in limitations):
        raise AIOutputError("报告缺少limitations数组")
    normalized["limitations"] = [value.strip()[:1000] for value in limitations[:8] if value.strip()]
    return normalized


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)


def enqueue_report_id(report_id: str) -> None:
    try:
        _redis().rpush(settings.ai_queue_name, report_id)
    except RedisError as exc:
        raise AIQueueError("AI报告队列暂不可用") from exc


def _provider_order() -> list[str]:
    providers = [settings.ai_primary_provider]
    if settings.ai_fallback_provider != "disabled" and settings.ai_fallback_provider not in providers:
        providers.append(settings.ai_fallback_provider)
    return [provider for provider in providers if provider != "disabled"]


def process_report_job(report_id: str, providers: list[AIProvider] | None = None) -> str:
    with SessionLocal() as db:
        report = db.get(AIReport, report_id)
        if not report or report.status not in {"queued", "retrying"}:
            return "ignored"
        report.status = "running"
        report.started_at = datetime.now(timezone.utc)
        report.error_code = None
        report.error_message = None
        db.commit()
        system_prompt = _system_prompt(report.report_type)
        user_prompt = _user_prompt(report)

    provider_list = providers or [provider_from_name(name) for name in _provider_order()]
    failures: list[str] = []
    for provider in provider_list:
        try:
            result = provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)
            output = validate_report_output(_extract_json(result.content), report.evidence_ids)
            with SessionLocal() as db:
                current = db.get(AIReport, report_id)
                if not current:
                    return "failed"
                current.status = "completed"
                current.provider = result.provider
                current.model = result.model
                current.output_json = output
                current.usage_json = _compact_value(result.usage)
                current.finished_at = datetime.now(timezone.utc)
                current.error_code = None
                current.error_message = None
                db.commit()
            return "completed"
        except (AIProviderError, AIOutputError) as exc:
            failures.append(f"{provider.name}: {exc}")

    with SessionLocal() as db:
        current = db.get(AIReport, report_id)
        if not current:
            return "failed"
        current.status = "failed"
        current.error_code = "ALL_PROVIDERS_FAILED"
        current.error_message = "；".join(failures)[:2000] or "没有可用的AI提供方"
        current.finished_at = datetime.now(timezone.utc)
        db.commit()
    return "failed"
