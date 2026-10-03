"""Add attestation fields to enrollment

Revision ID: 9d4513e52561
Revises: None
Create Date: 2026-08-10 00:37:03.605424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d4513e52561'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('enrollments', sa.Column('device_public_key', sa.Text(), nullable=True))
    op.add_column('enrollments', sa.Column('attestation_cert_chain', sa.Text(), nullable=True))
    op.add_column('enrollments', sa.Column('attestation_verified', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('enrollments', sa.Column('device_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('enrollments', 'device_id')
    op.drop_column('enrollments', 'attestation_verified')
    op.drop_column('enrollments', 'attestation_cert_chain')
    op.drop_column('enrollments', 'device_public_key')
