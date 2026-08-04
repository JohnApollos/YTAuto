"""v1.5 schema additions: SourcePost, BackgroundAsset, User tables;
   Transcript.promo_segments, Transcript.source_post_id,
   Clip.source_post_id, Clip.background_asset_id,
   Channel.voice_profile columns.

Revision ID: 002_v1_5_schema
Revises: (check the existing versions folder for the current head)
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

# Adjust `down_revision` to the ID of your current latest migration.
# If there is no prior migration file, set it to None.
revision = '002_v1_5_schema'
branch_labels = None
depends_on = None


def _get_down_revision():
    """Will be set by the alembic stamp command or manually below."""
    pass


down_revision = 'bce26fc3618c'  # IMPORTANT: update this to your current head revision ID


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # New table: source_posts
    # -----------------------------------------------------------------------
    op.create_table(
        'source_posts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_source_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('content_sources.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('subreddit', sa.String(), nullable=True),
        sa.Column('narration_audio_key', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # New table: background_assets
    # -----------------------------------------------------------------------
    op.create_table(
        'background_assets',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('license_type', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('license_evidence_ref', sa.Text(), nullable=True),
        sa.Column('duration_s', sa.Float(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # New table: users
    # -----------------------------------------------------------------------
    op.create_table(
        'users',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='operator'),
        sa.Column('channel_scope', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )

    # -----------------------------------------------------------------------
    # Alter existing tables
    # -----------------------------------------------------------------------

    # Channel: add voice_profile
    op.add_column('channels', sa.Column('voice_profile', sa.String(), nullable=True))

    # Transcripts: make source_video_id nullable, add source_post_id + promo_segments
    op.alter_column('transcripts', 'source_video_id', nullable=True)
    op.add_column('transcripts',
        sa.Column('source_post_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('source_posts.id'), nullable=True))
    op.add_column('transcripts', sa.Column('promo_segments', sa.JSON(), nullable=True))

    # Clips: make clip_candidate_id nullable, add source_post_id + background_asset_id
    op.alter_column('clips', 'clip_candidate_id', nullable=True)
    op.add_column('clips',
        sa.Column('source_post_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('source_posts.id'), nullable=True))
    op.add_column('clips',
        sa.Column('background_asset_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('background_assets.id'), nullable=True))


def downgrade() -> None:
    # Clips
    op.drop_column('clips', 'background_asset_id')
    op.drop_column('clips', 'source_post_id')
    op.alter_column('clips', 'clip_candidate_id', nullable=False)

    # Transcripts
    op.drop_column('transcripts', 'promo_segments')
    op.drop_column('transcripts', 'source_post_id')
    op.alter_column('transcripts', 'source_video_id', nullable=False)

    # Channel
    op.drop_column('channels', 'voice_profile')

    # Tables
    op.drop_table('users')
    op.drop_table('background_assets')
    op.drop_table('source_posts')
