"""enable pgvector and add document_chunks with an HNSW index

Revision ID: b7c2d4e91a05
Revises: a8f39b5b008d
Create Date: 2026-11-06 13:54:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = 'b7c2d4e91a05'
down_revision: Union[str, Sequence[str], None] = 'a8f39b5b008d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('source', sa.String(300), nullable=False),
        sa.Column('page', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('embedding', Vector(768), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_document_chunks_source', 'document_chunks', ['source'])
    op.create_index('uq_document_chunks_hash', 'document_chunks', ['content_hash'], unique=True)
    op.create_index('ix_document_chunks_hnsw', 'document_chunks', ['embedding'], postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})


def downgrade() -> None:
    op.drop_table('document_chunks')
    op.execute('DROP EXTENSION IF EXISTS vector')
