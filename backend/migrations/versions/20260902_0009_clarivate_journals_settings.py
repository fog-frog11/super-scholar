"""add Clarivate WoS Journals API settings

Revision ID: 20260902_0009
Revises: 20260829_0008
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260902_0009"
down_revision = "20260829_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scholarly_data_settings") as batch:
        batch.add_column(sa.Column("clarivate_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("clarivate_api_key_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("clarivate_journal_limit", sa.Integer(), nullable=False, server_default="36"))


def downgrade() -> None:
    with op.batch_alter_table("scholarly_data_settings") as batch:
        batch.drop_column("clarivate_journal_limit")
        batch.drop_column("clarivate_api_key_encrypted")
        batch.drop_column("clarivate_enabled")
