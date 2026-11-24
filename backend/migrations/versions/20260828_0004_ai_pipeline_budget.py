"""add hierarchical AI pipeline budget settings

Revision ID: 20260828_0004
Revises: 20260827_0003
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0004"
down_revision = "20260827_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # V3.3 hierarchical analysis never uploads the full raw PDF.
    op.execute(sa.text("UPDATE integration_settings SET ai_send_direct_pdf = 0"))
    op.add_column("integration_settings", sa.Column("ai_chunk_text_chars", sa.Integer(), nullable=False, server_default="10000"))
    op.add_column("integration_settings", sa.Column("ai_chunk_output_tokens", sa.Integer(), nullable=False, server_default="1800"))
    op.add_column("integration_settings", sa.Column("ai_synthesis_max_chars", sa.Integer(), nullable=False, server_default="24000"))
    op.add_column("integration_settings", sa.Column("ai_max_provider_calls", sa.Integer(), nullable=False, server_default="8"))
    op.add_column("integration_settings", sa.Column("ai_visuals_per_chunk", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("integration_settings", sa.Column("ai_request_timeout_seconds", sa.Integer(), nullable=False, server_default="180"))


def downgrade() -> None:
    op.drop_column("integration_settings", "ai_request_timeout_seconds")
    op.drop_column("integration_settings", "ai_visuals_per_chunk")
    op.drop_column("integration_settings", "ai_max_provider_calls")
    op.drop_column("integration_settings", "ai_synthesis_max_chars")
    op.drop_column("integration_settings", "ai_chunk_output_tokens")
    op.drop_column("integration_settings", "ai_chunk_text_chars")
