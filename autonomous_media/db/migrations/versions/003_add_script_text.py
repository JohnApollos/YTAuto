"""add script_text column to source_posts

Revision ID: 003_add_script_text
Revises: 002_v1_5_schema
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

revision = '003_add_script_text'
down_revision = '002_v1_5_schema'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('source_posts', sa.Column('script_text', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('source_posts', 'script_text')
