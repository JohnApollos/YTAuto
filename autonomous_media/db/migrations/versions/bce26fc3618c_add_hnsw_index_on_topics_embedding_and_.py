"""Add HNSW index on topics.embedding and scheduled_at to jobs

Revision ID: bce26fc3618c
Revises: a1b2c3d4e5f6
Create Date: 2026-07-29 11:33:48.226365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bce26fc3618c'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS topics_embedding_hnsw ON topics USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS topics_embedding_hnsw")
    op.drop_column('jobs', 'scheduled_at')
