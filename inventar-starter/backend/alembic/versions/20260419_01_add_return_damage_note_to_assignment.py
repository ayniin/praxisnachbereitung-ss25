"""add return_damage_note to assignment

Revision ID: 20260419_01
Revises:
Create Date: 2026-04-19 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260419_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assignment", sa.Column("return_damage_note", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_assignment_return_damage_note_requires_returned_at",
        "assignment",
        "return_damage_note is null or returned_at is not null",
    )


def downgrade() -> None:
    op.drop_constraint("ck_assignment_return_damage_note_requires_returned_at", "assignment", type_="check")
    op.drop_column("assignment", "return_damage_note")
