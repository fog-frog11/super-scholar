"""add streaming transport setting

Revision ID: 20260828_0005
Revises: 20260828_0004
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0005"
down_revision = "20260828_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_settings",
        sa.Column("ai_streaming_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("integration_settings", "ai_streaming_enabled")
