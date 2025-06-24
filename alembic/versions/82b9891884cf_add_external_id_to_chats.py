"""add external_id to chats

Revision ID: 82b9891884cf
Revises: 20d2af714b53
Create Date: 2025-04-18 14:56:22.859013

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82b9891884cf'
down_revision: Union[str, None] = '20d2af714b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
