"""Add paid mode toggle to channels

Revision ID: 202603110001
Revises: 202603050001
Create Date: 2026-03-11 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202603110001"
down_revision: Union[str, Sequence[str], None] = "202603050001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "paid_mode_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("channels", "paid_mode_enabled")
