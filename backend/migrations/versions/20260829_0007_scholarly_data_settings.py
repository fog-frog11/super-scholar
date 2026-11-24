"""add scholarly data source settings

Revision ID: 20260829_0007
Revises: 20260828_0006
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260829_0007"
down_revision = "20260828_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scholarly_data_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("openalex_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("openalex_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("openalex_max_results", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("crossref_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("crossref_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("crossref_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("semantic_scholar_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("semantic_scholar_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("dblp_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("last_test_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scholarly_data_settings")
