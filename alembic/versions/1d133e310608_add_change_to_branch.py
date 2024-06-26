"""add change to branch

Revision ID: 1d133e310608
Revises: 3fc2e5d095c4
Create Date: 2023-08-08 10:14:48.760510

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1d133e310608'
down_revision = '3fc2e5d095c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('branch', sa.Column('services', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('branch', 'services')
    # ### end Alembic commands ###
