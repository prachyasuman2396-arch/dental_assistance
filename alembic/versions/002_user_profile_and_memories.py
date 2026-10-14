"""Migration: user_profiles and long_term_memories tables

Revision ID: 002_user_profile_and_memories
Revises: 001_initial_schema
Create Date: 2026-10-13 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_user_profile_and_memories'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. User Profiles table
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('preferred_name', sa.String(length=255), nullable=True),
        sa.Column('academic_institution', sa.String(length=255), nullable=True),
        sa.Column('academic_discipline', sa.String(length=255), nullable=True, server_default='General Studies'),
        sa.Column('current_level', sa.String(length=100), nullable=True, server_default='Undergraduate'),
        sa.Column('explanation_style', sa.String(length=100), nullable=True, server_default='intuitive_first'),
        sa.Column('learning_goals', sa.JSON(), nullable=True),
        sa.Column('preferences_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_profiles_user_id')
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'], unique=True)

    # 2. Long Term Memories table
    op.create_table(
        'long_term_memories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('memory_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('topic', sa.String(length=255), nullable=True),
        sa.Column('importance', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_long_term_memories_user_id', 'long_term_memories', ['user_id'], unique=False)
    op.create_index('ix_long_term_memories_memory_type', 'long_term_memories', ['memory_type'], unique=False)
    op.create_index('ix_lt_memories_user_type', 'long_term_memories', ['user_id', 'memory_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lt_memories_user_type', table_name='long_term_memories')
    op.drop_index('ix_long_term_memories_memory_type', table_name='long_term_memories')
    op.drop_index('ix_long_term_memories_user_id', table_name='long_term_memories')
    op.drop_table('long_term_memories')

    op.drop_index('ix_user_profiles_user_id', table_name='user_profiles')
    op.drop_table('user_profiles')
