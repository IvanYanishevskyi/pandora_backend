"""add external_id and db_id to chats

Revision ID: d34c96679298
Revises: 82b9891884cf
Create Date: 2025-04-18 15:00:51.082298

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd34c96679298'
down_revision: Union[str, None] = '82b9891884cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
