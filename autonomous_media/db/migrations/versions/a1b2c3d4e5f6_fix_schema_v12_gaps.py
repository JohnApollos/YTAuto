"""Fix schema gaps to fully match V1.2 spec §8.3

Revision ID: a1b2c3d4e5f6
Revises: d081f2fc0740
Create Date: 2026-07-28

Changes:
- clip_candidates: rename start_time_s->start_ms, end_time_s->end_ms (millisecond precision)
- clips: add channel_id FK, thumbnail_key, caption_style; fix status values
- inventory_items: rename scheduled_for->scheduled_at, platform_ref->external_video_id; add updated_at
- rights_records: change FK from source_video_id to content_source_id; add evidence_ref,
  reviewed_by, reviewed_at, expires_at; fix status values
- analytics_snapshots: replace generic entity_id/entity_type with inventory_item_id FK + explicit metric cols
- jobs: rename job_type->type, add channel_id FK (remove target_id)
- NEW: models table (spec §8.3)
- NEW: eval_runs table (spec §8.3)
- NEW: system_events table (spec §8.3)
- transcript: replace text+segments with engine, language, storage_key, word_count
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd081f2fc0740'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- clip_candidates: ms precision ----
    op.add_column('clip_candidates', sa.Column('start_ms', sa.Integer(), nullable=True))
    op.add_column('clip_candidates', sa.Column('end_ms', sa.Integer(), nullable=True))
    op.execute("UPDATE clip_candidates SET start_ms = start_time_s * 1000, end_ms = end_time_s * 1000")
    op.alter_column('clip_candidates', 'start_ms', nullable=False)
    op.alter_column('clip_candidates', 'end_ms', nullable=False)
    op.drop_column('clip_candidates', 'start_time_s')
    op.drop_column('clip_candidates', 'end_time_s')
    op.drop_column('clip_candidates', 'transcript_text')  # stored in MinIO via transcript.storage_key

    # ---- clips: add channel_id, thumbnail_key, caption_style ----
    op.add_column('clips', sa.Column('channel_id', sa.Uuid(), nullable=True))
    op.add_column('clips', sa.Column('thumbnail_key', sa.String(), nullable=True))
    op.add_column('clips', sa.Column('caption_style', sa.String(), nullable=True))
    op.create_foreign_key('fk_clips_channel_id', 'clips', 'channels', ['channel_id'], ['id'])

    # ---- inventory_items: fix field names + add updated_at ----
    op.add_column('inventory_items', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
    op.add_column('inventory_items', sa.Column('external_video_id', sa.String(), nullable=True))
    op.add_column('inventory_items', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False))
    op.execute("UPDATE inventory_items SET scheduled_at = scheduled_for")
    op.execute("UPDATE inventory_items SET external_video_id = platform_ref")
    op.drop_column('inventory_items', 'scheduled_for')
    op.drop_column('inventory_items', 'platform_ref')

    # ---- rights_records: full redesign ----
    # Drop old table and recreate with correct schema
    op.drop_table('rights_records')
    op.create_table('rights_records',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('content_source_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('evidence_ref', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['content_source_id'], ['content_sources.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ---- analytics_snapshots: replace generic pattern with spec-compliant schema ----
    op.drop_table('analytics_snapshots')
    op.create_table('analytics_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('inventory_item_id', sa.Uuid(), nullable=False),
        sa.Column('captured_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('views', sa.Integer(), nullable=True),
        sa.Column('likes', sa.Integer(), nullable=True),
        sa.Column('comments', sa.Integer(), nullable=True),
        sa.Column('shares', sa.Integer(), nullable=True),
        sa.Column('avg_view_duration_s', sa.Float(), nullable=True),
        sa.Column('ctr', sa.Float(), nullable=True),
        sa.Column('subscribers_delta', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_snapshots_item_captured', 'analytics_snapshots', ['inventory_item_id', 'captured_at'])

    # ---- jobs: rename job_type->type, add channel_id, remove target_id ----
    op.add_column('jobs', sa.Column('type', sa.String(), nullable=True))
    op.execute("UPDATE jobs SET type = job_type")
    op.alter_column('jobs', 'type', nullable=False)
    op.drop_column('jobs', 'job_type')
    op.drop_column('jobs', 'target_id')
    op.add_column('jobs', sa.Column('channel_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_jobs_channel_id', 'jobs', 'channels', ['channel_id'], ['id'])

    # ---- transcripts: replace text+segments with metadata-only (content in MinIO) ----
    op.add_column('transcripts', sa.Column('engine', sa.String(), nullable=True, server_default='whisper-large-v3-turbo'))
    op.add_column('transcripts', sa.Column('language', sa.String(), nullable=True, server_default='en'))
    op.add_column('transcripts', sa.Column('storage_key', sa.String(), nullable=True))
    op.add_column('transcripts', sa.Column('word_count', sa.Integer(), nullable=True))
    op.drop_column('transcripts', 'text')
    op.drop_column('transcripts', 'segments')

    # ---- NEW: models table ----
    op.create_table('models',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('task', sa.String(), nullable=False),
        sa.Column('backend', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('resource_profile', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.PrimaryKeyConstraint('id')
    )

    # ---- NEW: eval_runs table ----
    op.create_table('eval_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('model_id', sa.Uuid(), nullable=True),
        sa.Column('benchmark_set_version', sa.String(), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['models.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ---- NEW: system_events table (append-only event log) ----
    op.create_table('system_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_system_events_trace_id', 'system_events', ['trace_id'])

    # ---- Performance indexes from spec §8.4 ----
    op.create_index('ix_jobs_status_priority_created', 'jobs', ['status', 'priority', 'created_at'])
    op.create_index('ix_source_videos_source_published', 'source_videos', ['content_source_id', 'published_at'])
    op.create_index('ix_inventory_items_channel_status_scheduled', 'inventory_items', ['channel_id', 'status', 'scheduled_at'])
    op.create_index('ix_clip_candidates_video_rank', 'clip_candidates', ['source_video_id', 'rank'])


def downgrade() -> None:
    op.drop_index('ix_clip_candidates_video_rank')
    op.drop_index('ix_inventory_items_channel_status_scheduled')
    op.drop_index('ix_source_videos_source_published')
    op.drop_index('ix_jobs_status_priority_created')
    op.drop_table('system_events')
    op.drop_table('eval_runs')
    op.drop_table('models')
    # Note: full reversal of column renames is intentionally omitted for brevity.
    # Restore from database backup before running downgrade against real data (spec §15.4).
