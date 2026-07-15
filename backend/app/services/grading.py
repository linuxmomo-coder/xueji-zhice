from __future__ import annotations

import ast
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import sympy as sp

from app.models import QuestionAnswerRule, QuestionResponseField


@dataclass
class GradeOutcome:
    correct: bool
    score: Decimal
    normalized: dict[str, Any]
    details: dict[str, Any]


def normalize_text(value: Any, *, case_sensitive: bool = False) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if case_sensitive else text.casefold()


def normalize_math_source(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    replacements = {
        "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "—": "-",
        "π": "pi", "²": "^2", "³": "^3", "∶": ":",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = text.replace("\\sqrt", "sqrt")
    text = re.sub(r"sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    text = re.sub(r"√\s*\(([^()]+)\)", r"sqrt(\1)", text)
    text = re.sub(r"√\s*([A-Za-z0-9.]+)", r"sqrt(\1)", text)
    text = re.sub(r"(?<=[0-9A-Za-z)])(?=sqrt\()", "*", text)
    text = re.sub(r"(?<=[0-9)])(?=[A-Za-z(])", "*", text)
    return text.replace("^", "**")


_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
_ALLOWED_UNARY = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}
_ALLOWED_FUNCTIONS = {"sqrt": sp.sqrt, "abs": sp.Abs}
_ALLOWED_CONSTANTS = {"pi": sp.pi, "e": sp.E}


def _ast_to_sympy(node: ast.AST) -> sp.Expr:
    if isinstance(node, ast.Expression):
        return _ast_to_sympy(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return sp.Rational(str(node.value))
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTANTS:
            return _ALLOWED_CONSTANTS[node.id]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", node.id):
            return sp.Symbol(node.id)
        raise ValueError("不支持的变量名")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_ast_to_sympy(node.left), _ast_to_sympy(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_ast_to_sympy(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _ALLOWED_FUNCTIONS.get(node.func.id)
        if function and len(node.args) == 1 and not node.keywords:
            return function(_ast_to_sympy(node.args[0]))
    raise ValueError("表达式包含不允许的语法")


def parse_math_expression(value: Any) -> sp.Expr:
    source = normalize_math_source(value)
    if len(source) > 200 or not re.fullmatch(r"[0-9A-Za-z_+\-*/().,\s]*", source):
        raise ValueError("表达式包含不允许的字符")
    return _ast_to_sympy(ast.parse(source, mode="eval"))


def symbolic_equal(left: Any, right: Any) -> bool:
    try:
        return sp.simplify(parse_math_expression(left) - parse_math_expression(right)) == 0
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
        return False


def _extract_field_value(answer: dict[str, Any], field_key: str) -> Any:
    if field_key in answer:
        return answer[field_key]
    if "value" in answer and field_key in {"answer", "blank_1", "choice_1"}:
        return answer["value"]
    if "selected" in answer and field_key in {"answer", "choice_1"}:
        return answer["selected"]
    return None


def _grade_rule(value: Any, rule: QuestionAnswerRule) -> tuple[bool, Any, dict[str, Any]]:
    accepted = rule.accepted_values or []
    rule_type = rule.rule_type
    if rule_type == "choice_set":
        actual = value if isinstance(value, list) else [value]
        normalized = sorted(normalize_text(item, case_sensitive=True) for item in actual if item is not None)
        expected = sorted(normalize_text(item, case_sensitive=True) for item in accepted)
        return normalized == expected, normalized, {"expected_count": len(expected)}
    if rule_type in {"exact_text", "normalized_text"}:
        actual = normalize_text(value, case_sensitive=rule.case_sensitive)
        expected = [normalize_text(item, case_sensitive=rule.case_sensitive) for item in accepted]
        return actual in expected, actual, {"accepted": expected}
    if rule_type == "numeric_tolerance":
        actual_text = normalize_text(value, case_sensitive=True).rstrip("°")
        try:
            actual_number = Decimal(actual_text)
        except InvalidOperation:
            return False, actual_text, {"reason": "not_numeric"}
        absolute = rule.absolute_tolerance or Decimal("0")
        relative = rule.relative_tolerance or Decimal("0")
        for candidate in accepted:
            try:
                expected_number = Decimal(str(candidate).rstrip("°"))
            except InvalidOperation:
                continue
            difference = abs(actual_number - expected_number)
            allowed = max(absolute, abs(expected_number) * relative)
            if difference <= allowed:
                return True, str(actual_number), {"difference": str(difference), "allowed": str(allowed)}
        return False, str(actual_number), {"reason": "outside_tolerance"}
    if rule_type == "symbolic_equivalence":
        normalized = normalize_math_source(value)
        return any(symbolic_equal(value, candidate) for candidate in accepted), normalized, {"parser": "safe_ast_sympy"}
    if rule_type == "set_equivalence":
        actual = value if isinstance(value, list) else re.split(r"[,，;；|]", str(value))
        normalized = [normalize_text(item, case_sensitive=rule.case_sensitive) for item in actual]
        expected = [normalize_text(item, case_sensitive=rule.case_sensitive) for item in accepted]
        result = normalized == expected if rule.order_sensitive else sorted(normalized) == sorted(expected)
        return result, normalized, {"order_sensitive": rule.order_sensitive}
    return False, value, {"reason": "manual_review_required"}


def grade_answer(answer: dict[str, Any], fields: list[QuestionResponseField], total_score: Decimal) -> GradeOutcome:
    normalized: dict[str, Any] = {}
    details: dict[str, Any] = {"fields": []}
    earned = Decimal("0")
    all_correct = True
    for field in sorted(fields, key=lambda item: item.sort_order):
        raw_value = _extract_field_value(answer, field.field_key)
        if raw_value is None and field.required:
            all_correct = False
            normalized[field.field_key] = None
            details["fields"].append({"field_key": field.field_key, "correct": False, "reason": "missing"})
            continue
        field_correct = False
        field_normalized: Any = raw_value
        field_details: dict[str, Any] = {}
        for rule in field.rules:
            correct, candidate_normalized, candidate_details = _grade_rule(raw_value, rule)
            field_normalized, field_details = candidate_normalized, candidate_details
            if correct:
                field_correct = True
                break
        normalized[field.field_key] = field_normalized
        details["fields"].append({"field_key": field.field_key, "correct": field_correct, "details": field_details})
        if field_correct:
            earned += field.score_weight
        else:
            all_correct = False
    return GradeOutcome(correct=all_correct, score=min(earned, total_score) if total_score > 0 else earned, normalized=normalized, details=details)
