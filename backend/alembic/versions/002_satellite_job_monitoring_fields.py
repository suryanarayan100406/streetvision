"""Add satellite job monitoring fields.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "satellite_jobs",
        sa.Column("tiles_forwarded_to_inference", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "satellite_jobs",
        sa.Column("monitoring_only_tiles", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("satellite_jobs", "tiles_forwarded_to_inference", server_default=None)
    op.alter_column("satellite_jobs", "monitoring_only_tiles", server_default=None)


def downgrade() -> None:
    op.drop_column("satellite_jobs", "monitoring_only_tiles")
    op.drop_column("satellite_jobs", "tiles_forwarded_to_inference")