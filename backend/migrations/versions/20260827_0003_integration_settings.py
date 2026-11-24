"""add application integration settings

Revision ID: 20260827_0003
Revises: 20260826_0002
Create Date: 2026-08-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_0003"
down_revision = "20260826_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ai_provider", sa.String(length=32), nullable=False, server_default="openai"),
        sa.Column("ai_base_url", sa.Text(), nullable=False, server_default="https://api.openai.com/v1"),
        sa.Column("ai_model", sa.String(length=160), nullable=False, server_default="gpt-5.6"),
        sa.Column("ai_protocol", sa.String(length=32), nullable=False, server_default="responses"),
        sa.Column("ai_output_mode", sa.String(length=32), nullable=False, server_default="json_schema"),
        sa.Column("ai_reasoning_effort", sa.String(length=24), nullable=False, server_default="medium"),
        sa.Column("ai_reasoning_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("ai_supports_vision", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_supports_files", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_send_direct_pdf", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_max_text_chars", sa.Integer(), nullable=False, server_default="220000"),
        sa.Column("ai_max_visual_assets", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("ai_max_pdf_files", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("ai_max_output_tokens", sa.Integer(), nullable=False, server_default="12000"),
        sa.Column("tesseract_cmd", sa.Text(), nullable=False, server_default=""),
        sa.Column("ocr_languages", sa.String(length=120), nullable=False, server_default="eng"),
        sa.Column("ocr_min_native_text_chars", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("last_ai_test_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("integration_settings")
