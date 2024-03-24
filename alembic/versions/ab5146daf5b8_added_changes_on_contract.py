"""added changes on contract

Revision ID: ab5146daf5b8
Revises: b3f3fc63bddd
Create Date: 2023-09-21 13:14:41.213943

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'ab5146daf5b8'
down_revision = 'b3f3fc63bddd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('contract', 'rate')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('contract', sa.Column('rate', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
