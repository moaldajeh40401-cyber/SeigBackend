"""add email verification

Revision ID: 20261001_email_verification
Revises: 5e5b3df5285e
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_email_verification"
down_revision = "5e5b3df5285e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("users", "is_email_verified")