"""PublishedAsset

Revision ID: 9213e267193c
Revises: c3e2855da3f6
Create Date: 2026-07-28 09:51:48.947088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9213e267193c'
down_revision: Union[str, Sequence[str], None] = 'c3e2855da3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
