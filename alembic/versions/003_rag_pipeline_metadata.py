"""Migration: RAG pipeline metadata for parent-child retrieval, content deduplication, and section tracking

Revision ID: 003_rag_pipeline_metadata
Revises: 002_user_profile_and_memories
Create Date: 2026-10-13 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_rag_pipeline_metadata'
down_revision = '002_user_profile_and_memories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add metadata tracking columns to documents
    op.add_column('documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('documents', sa.Column('mime_type', sa.String(length=100), nullable=True))
    op.add_column('documents', sa.Column('embedding_model', sa.String(length=128), nullable=True))
    op.create_index('ix_documents_content_hash', 'documents', ['user_id', 'content_hash'], unique=False)

    # 2. Add hierarchical and structure-aware columns to document_chunks
    op.add_column('document_chunks', sa.Column('parent_chunk_id', sa.String(length=36), nullable=True))
    op.add_column('document_chunks', sa.Column('section_title', sa.String(length=255), nullable=True))
    op.add_column('document_chunks', sa.Column('page_start', sa.Integer(), nullable=True))
    op.add_column('document_chunks', sa.Column('page_end', sa.Integer(), nullable=True))
    op.create_index('ix_doc_chunks_parent_chunk_id', 'document_chunks', ['parent_chunk_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_doc_chunks_parent_chunk_id', table_name='document_chunks')
    op.drop_column('document_chunks', 'page_end')
    op.drop_column('document_chunks', 'page_start')
    op.drop_column('document_chunks', 'section_title')
    op.drop_column('document_chunks', 'parent_chunk_id')

    op.drop_index('ix_documents_content_hash', table_name='documents')
    op.drop_column('documents', 'embedding_model')
    op.drop_column('documents', 'mime_type')
    op.drop_column('documents', 'content_hash')
