"""RenderedAsset

Revision ID: c3e2855da3f6
Revises: c9be2edbff0c
Create Date: 2026-07-28 09:45:29.679046

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e2855da3f6'
down_revision: Union[str, Sequence[str], None] = 'c9be2edbff0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
