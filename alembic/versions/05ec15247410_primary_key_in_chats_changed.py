"""Primary key in chats changed

Revision ID: 05ec15247410
Revises: 7f2adc73579b
Create Date: 2025-02-26 01:07:43.095475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05ec15247410'
down_revision: Union[str, None] = '7f2adc73579b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
