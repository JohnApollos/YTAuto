"""CandidateClip and EvaluationScore

Revision ID: c9be2edbff0c
Revises: 5947274ac01b
Create Date: 2026-07-28 09:40:12.715976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9be2edbff0c'
down_revision: Union[str, Sequence[str], None] = '5947274ac01b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
