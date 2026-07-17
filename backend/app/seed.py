from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Family,
    FamilyMember,
    GuardianConsent,
    Question,
    QuestionAnswerRule,
    QuestionOption,
    QuestionResponseField,
    QuestionVersion,
    Student,
    User,
)
from app.services.legal import (
    CURRENT_CHILD_POLICY_VERSION,
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
    REQUIRED_CHILD_SCOPE,
)


def _checksum(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(User.id).where(User.email == "parent@example.com")):
        return

    parent = User(email="parent@example.com", password_hash=hash_password("Parent123!"), role="parent", display_name="演示家长")
    student_user = User(email="student@example.com", password_hash=hash_password("Student123!"), role="student", display_name="林小雨")
    admin = User(email="admin@example.com", password_hash=hash_password("Admin123!"), role="admin", display_name="平台管理员")
    db.add_all([parent, student_user, admin])
    db.flush()

    family = Family(name="林小雨家庭", primary_guardian_user_id=parent.id)
    db.add(family)
    db.flush()
    db.add_all([
        FamilyMember(family_id=family.id, user_id=parent.id, relation_type="guardian", is_primary_guardian=True, permissions={"manage_students": True, "confirm_documents": True}),
        FamilyMember(family_id=family.id, user_id=student_user.id, relation_type="student", is_primary_guardian=False, permissions={"practice": True, "upload_documents": True}),
        GuardianConsent(
            guardian_user_id=parent.id,
            family_id=family.id,
            student_id=None,
            terms_version=CURRENT_TERMS_VERSION,
            privacy_version=CURRENT_PRIVACY_VERSION,
            child_policy_version=CURRENT_CHILD_POLICY_VERSION,
            consent_scope=REQUIRED_CHILD_SCOPE,
            accepted_at=datetime.now(timezone.utc),
            ip_address="127.0.0.1",
            user_agent="demo-seed",
        ),
    ])
    student = Student(
        family_id=family.id, user_id=student_user.id, nickname="林小雨", school_system="6-3",
        current_grade=8, current_term="2026-2027 第一学期", region="广东省广州市",
        daily_minutes_limit=50, created_by_user_id=parent.id,
    )
    db.add(student)
    db.flush()

    def add_question(code: str, display_type: str, stem: str, options: list[tuple[str, str]], field_type: str,
                     rule_type: str, accepted: list, answer_summary: str, explanation: str,
                     difficulty: int = 2, case_sensitive: bool = False) -> None:
        question = Question(
            question_code=code,
            subject="数学" if code.startswith("MATH") else "英语",
            base_grade=8,
            lifecycle_status="active",
            source_type="self_built",
            copyright_status="owned",
            created_by_user_id=admin.id,
            first_published_at=datetime.now(timezone.utc),
        )
        db.add(question)
        db.flush()
        version = QuestionVersion(
            question_id=question.id,
            version_no=1,
            display_type=display_type,
            stem_content={"blocks": [{"type": "text", "value": stem}]},
            explanation_content={"blocks": [{"type": "text", "value": explanation}]},
            difficulty=difficulty,
            cognitive_level="application",
            estimated_seconds=120,
            scoring_mode="rule",
            total_score=Decimal("1.00"),
            common_errors=[],
            answer_summary=answer_summary,
            content_checksum=_checksum(code, stem, answer_summary),
            review_status="approved",
            publication_status="published",
            reviewed_by_user_id=admin.id,
            reviewed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        db.flush()
        for index, (key, value) in enumerate(options, start=1):
            db.add(QuestionOption(
                question_version_id=version.id,
                option_key=key,
                content={"blocks": [{"type": "text", "value": value}]},
                sort_order=index,
            ))
        field = QuestionResponseField(
            question_version_id=version.id,
            field_key="answer",
            field_type=field_type,
            sort_order=1,
            score_weight=Decimal("1.00"),
            input_config={"math_keyboard": field_type == "math_expression"},
        )
        db.add(field)
        db.flush()
        db.add(QuestionAnswerRule(
            response_field_id=field.id,
            rule_type=rule_type,
            accepted_values=accepted,
            normalization_profile="math_zh_v1" if field_type == "math_expression" else "text_zh_v1",
            case_sensitive=case_sensitive,
            allow_fullwidth_equivalent=True,
            parser_profile="safe_ast_sympy" if rule_type == "symbolic_equivalence" else None,
        ))
        question.current_version_id = version.id

    add_question("MATH-G8-CHOICE-0001", "single_choice", "若一个三角形的两个内角分别为50°和60°，第三个内角是多少？",
                 [("A", "60°"), ("B", "70°"), ("C", "80°"), ("D", "90°")], "single_choice",
                 "choice_set", ["B"], "B", "三角形内角和为180°，第三个角为180°-50°-60°=70°。", 1)
    add_question("MATH-G8-RADICAL-0001", "fill_blank", "化简：√27 = ____。", [], "math_expression",
                 "symbolic_equivalence", ["3√3"], "3√3", "√27=√(9×3)=3√3。", 2)
    add_question("ENG-G8-TEXT-0001", "fill_blank", "She ____ to school every Monday. (go)", [], "text",
                 "normalized_text", ["goes"], "goes", "主语She为第三人称单数，go变为goes。", 1, False)
    db.commit()
