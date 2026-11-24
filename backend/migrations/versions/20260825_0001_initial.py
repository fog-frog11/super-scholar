"""initial Super Scholar backend schema

Revision ID: 20260825_0001
Revises:
Create Date: 2026-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260825_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=True),
        sa.Column("preferences_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_run_json", sa.JSON(), nullable=True),
        sa.Column("comparison_venue_ids_json", sa.JSON(), nullable=False),
        sa.Column("selected_venue_id", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_name", "projects", ["name"], unique=False)
    op.create_index("ix_projects_status", "projects", ["status"], unique=False)
    op.create_index("ix_projects_archived", "projects", ["archived"], unique=False)
    op.create_index("ix_projects_updated_at", "projects", ["updated_at"], unique=False)

    op.create_table(
        "materials",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("project_id", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=160), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("text_storage_path", sa.Text(), nullable=True),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_materials_project_id", "materials", ["project_id"], unique=False)
    op.create_index("ix_materials_sha256", "materials", ["sha256"], unique=False)

    op.create_table(
        "venue_cache",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=240), nullable=False),
        sa.Column("source_tier", sa.String(length=40), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("kind"),
    )


def downgrade() -> None:
    op.drop_table("venue_cache")
    op.drop_index("ix_materials_sha256", table_name="materials")
    op.drop_index("ix_materials_project_id", table_name="materials")
    op.drop_table("materials")
    op.drop_index("ix_projects_updated_at", table_name="projects")
    op.drop_index("ix_projects_archived", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
