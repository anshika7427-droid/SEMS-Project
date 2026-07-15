"""merge two heads

Revision ID: e8226b01c01b
Revises: e5f86a563b66, f167df234b21
Create Date: 2026-07-15 16:53:17.491864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8226b01c01b'
down_revision: Union[str, Sequence[str], None] = ('e5f86a563b66', 'f167df234b21')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
