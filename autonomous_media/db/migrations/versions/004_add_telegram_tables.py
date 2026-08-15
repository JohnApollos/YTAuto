"""add telegram_configs and telegram_delivery_logs tables

Revision ID: 004_add_telegram_tables
Revises: 003_add_script_text
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_add_telegram_tables'
down_revision = '003_add_script_text'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # telegram_configs
    op.create_table(
        'telegram_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_token', sa.String(), nullable=True),
        sa.Column('chat_id', sa.String(), nullable=True),
        sa.Column('allowed_chat_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('categories', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('quiet_hours_start', sa.String(), nullable=False, server_default='23:00'),
        sa.Column('quiet_hours_end', sa.String(), nullable=False, server_default='07:00'),
        sa.Column('timezone', sa.String(), nullable=False, server_default='Africa/Nairobi'),
        sa.Column('dedupe_window_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('quota_warning_threshold', sa.Integer(), nullable=False, server_default='70'),
        sa.Column('quota_critical_threshold', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # telegram_delivery_logs
    op.create_table(
        'telegram_delivery_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('notification_id', sa.String(), nullable=False, index=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False, server_default='INFO'),
        sa.Column('dedupe_key', sa.String(), nullable=True, index=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='queued'),
        sa.Column('telegram_message_id', sa.Integer(), nullable=True),
        sa.Column('chat_id', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
    )

def downgrade() -> None:
    op.drop_table('telegram_delivery_logs')
    op.drop_table('telegram_configs')
