"""add change to contract

Revision ID: 3fc2e5d095c4
Revises: 586030aa846b
Create Date: 2023-08-07 14:42:58.228410

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3fc2e5d095c4'
down_revision = '586030aa846b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('contract', sa.Column('services', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('contract', 'services')
    # ### end Alembic commands ###
