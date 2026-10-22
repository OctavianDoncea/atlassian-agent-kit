"""add eval_runs.duration_ms

Revision ID: c4a1b7e82d10
Revises: e6d2e4569a3c
Create Date: 2026-10-22 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a1b7e82d10'
down_revision: Union[str, Sequence[str], None] = 'e6d2e4569a3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('eval_runs', sa.Column('duration_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('eval_runs', 'duration_ms')
