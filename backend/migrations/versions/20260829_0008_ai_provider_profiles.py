"""persist AI provider profiles independently

Revision ID: 20260829_0008
Revises: 20260829_0007
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260829_0008"
down_revision = "20260829_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_profiles",
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("protocol", sa.String(length=32), nullable=False, server_default="responses"),
        sa.Column("output_mode", sa.String(length=32), nullable=False, server_default="json_object"),
        sa.Column("reasoning_effort", sa.String(length=24), nullable=False, server_default="medium"),
        sa.Column("reasoning_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("streaming_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("transport_profile", sa.String(length=32), nullable=False, server_default="auto"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supports_files", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("send_direct_pdf", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_test_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("provider"),
    )

    # Preserve the user's currently configured provider exactly. Other provider
    # profiles are created lazily from real defaults when the user saves them.
    bind = op.get_bind()
    row = bind.execute(sa.text("""
        SELECT ai_provider, ai_base_url, ai_model, ai_protocol, ai_output_mode,
               ai_reasoning_effort, ai_reasoning_enabled, ai_streaming_enabled,
               ai_transport_profile, ai_api_key_encrypted, ai_supports_vision,
               ai_supports_files, ai_send_direct_pdf, last_ai_test_json, updated_at
        FROM integration_settings WHERE id = 1
    """)).mappings().first()
    if row and row.get("ai_provider") in {"openai", "deepseek", "custom"}:
        bind.execute(sa.text("""
            INSERT INTO ai_provider_profiles (
                provider, base_url, model, protocol, output_mode, reasoning_effort,
                reasoning_enabled, streaming_enabled, transport_profile,
                api_key_encrypted, supports_vision, supports_files, send_direct_pdf,
                last_test_json, updated_at
            ) VALUES (
                :provider, :base_url, :model, :protocol, :output_mode, :reasoning_effort,
                :reasoning_enabled, :streaming_enabled, :transport_profile,
                :api_key_encrypted, :supports_vision, :supports_files, :send_direct_pdf,
                :last_test_json, :updated_at
            )
        """), {
            "provider": row["ai_provider"],
            "base_url": row["ai_base_url"],
            "model": row["ai_model"],
            "protocol": row["ai_protocol"],
            "output_mode": row["ai_output_mode"],
            "reasoning_effort": row["ai_reasoning_effort"],
            "reasoning_enabled": row["ai_reasoning_enabled"],
            "streaming_enabled": row["ai_streaming_enabled"],
            "transport_profile": row["ai_transport_profile"],
            "api_key_encrypted": row["ai_api_key_encrypted"],
            "supports_vision": row["ai_supports_vision"],
            "supports_files": row["ai_supports_files"],
            "send_direct_pdf": row["ai_send_direct_pdf"],
            "last_test_json": row["last_ai_test_json"],
            "updated_at": row["updated_at"],
        })


def downgrade() -> None:
    op.drop_table("ai_provider_profiles")
