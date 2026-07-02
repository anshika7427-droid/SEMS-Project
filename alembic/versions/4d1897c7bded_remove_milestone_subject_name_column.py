"""remove_milestone_subject_name_column

Revision ID: 4d1897c7bded
Revises: 73212fca90b8
Create Date: 2026-07-03 01:46:09.686341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d1897c7bded'
down_revision: Union[str, Sequence[str], None] = '73212fca90b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('milestones', schema=None) as batch_op:
        batch_op.drop_column('subject_name')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('milestones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subject_name', sa.VARCHAR(), nullable=True))
    
    # Backfill subject_name from subjects table
    op.execute(
        "UPDATE milestones SET subject_name = (SELECT name FROM subjects WHERE subjects.id = milestones.subject_id)"
    )
