import uuid
from autonomous_media.db.models import Task
from autonomous_media.workers.evaluate import EvaluateWorker

def run_test():
    print("=== Testing Phase 2 Evaluation Engine ===")
    
    mock_clips = [
        {
            "id": str(uuid.uuid4()),
            "transcript_text": "Hey guys, today we are going to build an AI agent from scratch. It's going to blow your mind!"
        },
        {
            "id": str(uuid.uuid4()),
            "transcript_text": "The reason most startups fail isn't technology. It's distribution. You can have the best product, but if nobody knows about it, you're dead."
        },
        {
            "id": str(uuid.uuid4()),
            "transcript_text": "So I was walking down the street the other day and I saw this bird. Anyway, back to the main topic..."
        }
    ]

    eval_task = Task(
        id=uuid.uuid4(),
        task_type="evaluate_clips",
        payload={
            "source_video_id": str(uuid.uuid4()),
            "_mock_clips": mock_clips
        },
        attempts=0,
        max_attempts=3
    )

    eval_worker = EvaluateWorker()
    try:
        result = eval_worker.run(eval_task)
        print("Evaluation successful:", result.summary())
    except Exception as e:
        print("Evaluation failed:", e)

if __name__ == "__main__":
    run_test()
