"""Add changes

Revision ID: 12a373d592f9
Revises: 277377bf627a
Create Date: 2022-08-19 12:59:27.383900

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '12a373d592f9'
down_revision = '277377bf627a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('employeeentry', sa.Column('image', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('invoice', sa.Column('invoice_ebm', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('user', sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'role')
    op.drop_column('invoice', 'invoice_ebm')
    op.drop_column('employeeentry', 'image')
    # ### end Alembic commands ###
