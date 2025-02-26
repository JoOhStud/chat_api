"""Manual migration: update table key

Revision ID: 015d0f979286
Revises: 05ec15247410
Create Date: 2025-02-26 01:18:26.585318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015d0f979286'
down_revision: Union[str, None] = '05ec15247410'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_index('ix_chats_name', table_name='chats')
    
def downgrade():
    op.create_index('ix_chats_name', 'chats', ['name'], unique=True)