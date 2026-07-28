"""Workflow schema

Revision ID: 5947274ac01b
Revises: c6ac6a26f16d
Create Date: 2026-07-28 09:25:26.464442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5947274ac01b'
down_revision: Union[str, Sequence[str], None] = 'c6ac6a26f16d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
