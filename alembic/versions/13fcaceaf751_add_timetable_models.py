"""Add timetable models

Revision ID: 13fcaceaf751
Revises: 0015_review_cards
Create Date: 2026-06-30 10:12:33.007641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '13fcaceaf751'
down_revision: Union[str, None] = '0015_review_cards'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def upgrade() -> None:
    if not _has_table('timetables'):
        op.create_table(
            'timetables',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('timetables', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_timetables_id'), ['id'], unique=False)

    if not _has_table('timetable_tasks'):
        op.create_table(
            'timetable_tasks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('timetable_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['timetable_id'], ['timetables.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('timetable_tasks', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_timetable_tasks_id'), ['id'], unique=False)

    if not _has_table('tracked_sessions'):
        op.create_table(
            'tracked_sessions',
            sa.Column('session_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('task_id', sa.Integer(), nullable=True),
            sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
            sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('category', sa.String(), nullable=True),
            sa.Column('productivity_score', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['timetable_tasks.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('session_id'),
        )
        with op.batch_alter_table('tracked_sessions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_tracked_sessions_session_id'), ['session_id'], unique=False)


def downgrade() -> None:
    if _has_table('tracked_sessions'):
        with op.batch_alter_table('tracked_sessions', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_tracked_sessions_session_id'))
        op.drop_table('tracked_sessions')

    if _has_table('timetable_tasks'):
        with op.batch_alter_table('timetable_tasks', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_timetable_tasks_id'))
        op.drop_table('timetable_tasks')

    if _has_table('timetables'):
        with op.batch_alter_table('timetables', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_timetables_id'))
        op.drop_table('timetables')
