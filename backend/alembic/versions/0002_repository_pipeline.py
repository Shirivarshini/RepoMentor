"""Repository snapshots, source intelligence, embeddings and Q&A.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
