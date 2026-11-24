"""add text-first provider transport profile

Revision ID: 20260828_0006
Revises: 20260828_0005
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0006"
down_revision = "20260828_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_settings",
        sa.Column("ai_transport_profile", sa.String(length=32), nullable=False, server_default="auto"),
    )
    # Migrate only the exact old DeepSeek preset from V3.1-V3.5. User-customized
    # DeepSeek configurations are left untouched. Chat Completions + JSON Object is
    # the more mature common text path and works with both V4-Flash and V4-Pro.
    op.execute(sa.text(
        "UPDATE integration_settings SET ai_protocol='chat_completions', ai_output_mode='json_object' "
        "WHERE ai_provider='deepseek' AND ai_base_url='https://api.deepseek.com' "
        "AND ai_model='deepseek-v4-flash' AND ai_protocol='responses' AND ai_output_mode='json_schema'"
    ))


def downgrade() -> None:
    op.drop_column("integration_settings", "ai_transport_profile")
