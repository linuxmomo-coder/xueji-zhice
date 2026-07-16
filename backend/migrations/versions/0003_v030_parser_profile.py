"""Normalize legacy symbolic parser profiles.

Revision ID: 0003_v030_parser_profile
Revises: 0002_v030_learning
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_v030_parser_profile"
down_revision = "0002_v030_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE question_answer_rules
            SET parser_profile = 'safe_ast_sympy'
            WHERE rule_type = 'symbolic_equivalence'
              AND parser_profile = 'math_basic_v1'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE question_answer_rules
            SET parser_profile = 'math_basic_v1'
            WHERE rule_type = 'symbolic_equivalence'
              AND parser_profile = 'safe_ast_sympy'
            """
        )
    )
