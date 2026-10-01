"""remove the unused email verification flag

Revision ID: 20261001_remove_email_verification
Revises: 20261001_email_verification
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_remove_email_verification"
down_revision = "20261001_email_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("users", "is_email_verified")


def downgrade():
    op.add_column(
        "users",
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
