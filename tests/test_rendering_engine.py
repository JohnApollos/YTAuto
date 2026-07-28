import uuid
from autonomous_media.db.models import Task
from autonomous_media.workers.render import RenderWorker

def run_test():
    print("=== Testing Phase 3 Rendering Engine ===")

    clip_id = str(uuid.uuid4())
    render_task = Task(
        id=uuid.uuid4(),
        task_type="render_video",
        payload={
            "candidate_clip_id": clip_id,
            "_mock_clip_data": {
                "start_time_s": 0,
                "end_time_s": 15,
                "transcript_text": "This is a test of the emergency rendering system.",
                "source_video_key": "dummy_missing_video.mp4"
            }
        },
        attempts=0,
        max_attempts=3
    )

    worker = RenderWorker()
    try:
        result = worker.run(render_task)
        print("Rendering successful:", result.summary())
    except Exception as e:
        print("Rendering failed:", e)

if __name__ == "__main__":
    run_test()
