import uuid
from autonomous_media.db.models import Task
from autonomous_media.workers.publish import PublishWorker
from autonomous_media.youtube.client import QuotaExhaustedError

def run_test():
    print("=== Testing Phase 4 Publishing Engine ===")

    asset_id = str(uuid.uuid4())
    publish_task = Task(
        id=uuid.uuid4(),
        task_type="publish_video",
        payload={
            "rendered_asset_id": asset_id,
            "_mock_video_path": "dummy_missing_video.mp4"
        },
        attempts=0,
        max_attempts=3
    )

    worker = PublishWorker()
    try:
        result = worker.run(publish_task)
        print("Publishing successful:", result.summary())
    except Exception as e:
        print("Publishing failed:", e)

if __name__ == "__main__":
    run_test()
