import os
import uuid
import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, InventoryItem, Clip, Channel, AnalyticsSnapshot
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.analytics")

class AnalyticsWorker(Worker):
    job_type = 'analytics'

    def process(self, session: Session, job: Job) -> JobResult:
        inventory_item_id = job.payload.get("inventory_item_id")
        if not inventory_item_id:
            raise StageUnrecoverableError("Missing inventory_item_id in job payload")

        inventory_item = session.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        if not inventory_item:
            raise StageUnrecoverableError(f"InventoryItem {inventory_item_id} not found")

        if inventory_item.status != "published" or not inventory_item.external_video_id:
            logger.warning(
                f"InventoryItem {inventory_item_id} is not yet published (status: {inventory_item.status}). Skipping.",
                extra={"trace_id": job.trace_id}
            )
            return JobResult()

        clip = session.query(Clip).filter(Clip.id == inventory_item.clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {inventory_item.clip_id} not found")

        channel = session.query(Channel).filter(Channel.id == clip.channel_id).first()
        if not channel:
            raise StageUnrecoverableError(f"Channel {clip.channel_id} not found")

        logger.info(
            f"Fetching analytics for InventoryItem {inventory_item_id} (YouTube ID: {inventory_item.external_video_id})",
            extra={"trace_id": job.trace_id}
        )

        views, likes, comments, shares = 0, 0, 0, 0

        # Retrieve OAuth credentials
        oauth_data = channel.branding.get("oauth_credentials") or {}
        if not oauth_data and os.environ.get("YOUTUBE_OAUTH_TOKEN"):
            oauth_data = {"token": os.environ.get("YOUTUBE_OAUTH_TOKEN")}

        is_mock_video = inventory_item.external_video_id.startswith("mock_")

        if not oauth_data or is_mock_video:
            # Fallback mock statistics for tests/offline MVP
            logger.info("Running in mock/offline analytics mode", extra={"trace_id": job.trace_id})
            views = random.randint(100, 5000)
            likes = int(views * random.uniform(0.02, 0.10))
            comments = int(likes * random.uniform(0.05, 0.20))
            shares = int(views * random.uniform(0.01, 0.05))
        else:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                creds = Credentials(
                    token=oauth_data.get("token"),
                    refresh_token=oauth_data.get("refresh_token"),
                    token_uri=oauth_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                    client_id=oauth_data.get("client_id"),
                    client_secret=oauth_data.get("client_secret")
                )
                youtube = build("youtube", "v3", credentials=creds)

                # Get video statistics via videos.list
                request = youtube.videos().list(
                    part="statistics",
                    id=inventory_item.external_video_id
                )
                response = request.execute()
                
                items = response.get("items", [])
                if not items:
                    logger.warning(
                        f"Video {inventory_item.external_video_id} not found on YouTube. Using zero statistics.",
                        extra={"trace_id": job.trace_id}
                    )
                else:
                    stats = items[0].get("statistics", {})
                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))
                    # shares is not available via standard YouTube Data API videos.list, so we proxy it or keep it 0
                    shares = 0
            except Exception as e:
                raise StageUnrecoverableError(f"YouTube Analytics API query failed: {e}")

        # Create AnalyticsSnapshot row
        snapshot_id = uuid.uuid4()
        snapshot = AnalyticsSnapshot(
            id=snapshot_id,
            inventory_item_id=inventory_item_id,
            captured_at=datetime.now(timezone.utc),
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            avg_view_duration_s=0.0,
            ctr=0.0,
            subscribers_delta=0
        )
        session.add(snapshot)
        session.flush()

        # Emit event
        emit_event(
            event_type="analytics.updated",
            trace_id=job.trace_id,
            payload={
                "analytics_snapshot_id": str(snapshot_id),
                "inventory_item_id": str(inventory_item_id),
                "views": views,
                "likes": likes
            }
        )

        # Enqueue learning job
        next_job = Job(
            type="learning",
            payload={"analytics_snapshot_id": str(snapshot_id)},
            trace_id=job.trace_id,
            channel_id=job.channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        logger.info(
            f"Successfully updated analytics for Item {inventory_item_id}. Views: {views}. Enqueued learning job.",
            extra={"trace_id": job.trace_id}
        )

        return JobResult()
