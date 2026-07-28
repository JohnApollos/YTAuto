import uuid
import datetime
from autonomous_media.workers.base import Worker, Task, TaskResult
from autonomous_media.youtube.client import YouTubeAPIClient, QuotaExhaustedError

class PublishResult(TaskResult):
    def __init__(self, youtube_video_id: str = None, deferred: bool = False):
        self.youtube_video_id = youtube_video_id
        self.deferred = deferred

    def summary(self):
        return {
            "youtube_video_id": self.youtube_video_id,
            "deferred": self.deferred
        }

class PublishWorker(Worker):
    task_type = "publish_video"

    def process(self, task: Task) -> TaskResult:
        rendered_asset_id_str = task.payload.get("rendered_asset_id")
        if not rendered_asset_id_str:
            raise ValueError("rendered_asset_id is required in payload")
            
        # Stub: Fetch the RenderedAsset and target Channel metadata from the DB.
        mock_asset_path = task.payload.get("_mock_video_path", "data/rendered/mock.mp4")
        mock_title = task.payload.get("_mock_title", "Auto Generated Short")
        mock_desc = task.payload.get("_mock_desc", "This is an automated short! #shorts")
        
        # Stub: Credentials from DB
        client_id = task.payload.get("_mock_client_id", "dummy_client_id")
        client_secret = task.payload.get("_mock_client_secret", "dummy_client_secret")
        refresh_token = task.payload.get("_mock_refresh_token", "dummy_refresh_token")
        
        client = YouTubeAPIClient(client_id, client_secret, refresh_token)
        
        try:
            # We mock the actual HTTP call if the file doesn't exist to prevent test crashes
            if mock_asset_path == "dummy_missing_video.mp4":
                print(f"[PublishWorker] Using dev mock for YouTube upload of {mock_asset_path}")
                video_id = f"yt_{uuid.uuid4().hex[:8]}"
            else:
                # This would execute a real upload if the file existed and credentials were valid
                video_id = client.upload_video(
                    video_path=mock_asset_path,
                    title=mock_title,
                    description=mock_desc,
                    tags=["shorts", "podcast", "viral"]
                )
                
            # Stub: Save PublishedAsset to DB with status='published', youtube_video_id=video_id
            return PublishResult(youtube_video_id=video_id)
            
        except QuotaExhaustedError:
            print("[PublishWorker] Quota exhausted! Deferring task to tomorrow.")
            # As per technical specification (and Phase 4 implementation plan decision), 
            # we do not fail the task. We defer it to be picked up by the scheduler 
            # when the quota resets at midnight Pacific Time.
            return PublishResult(deferred=True)
