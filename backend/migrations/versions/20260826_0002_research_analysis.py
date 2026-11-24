"""add research analysis runs

Revision ID: 20260826_0002
Revises: 20260825_0001
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0002"
down_revision = "20260825_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_analysis_runs",
        sa.Column("id", sa.String(length=96), primary_key=True),
        sa.Column("project_id", sa.String(length=96), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="ai"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=80), nullable=False, server_default="queued"),
        sa.Column("message", sa.Text(), nullable=False, server_default="等待分析"),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_research_analysis_runs_project_id", "research_analysis_runs", ["project_id"])
    op.create_index("ix_research_analysis_runs_status", "research_analysis_runs", ["status"])
    op.create_index("ix_research_analysis_runs_updated_at", "research_analysis_runs", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_research_analysis_runs_updated_at", table_name="research_analysis_runs")
    op.drop_index("ix_research_analysis_runs_status", table_name="research_analysis_runs")
    op.drop_index("ix_research_analysis_runs_project_id", table_name="research_analysis_runs")
    op.drop_table("research_analysis_runs")
