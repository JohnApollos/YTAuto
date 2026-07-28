import uuid
import os
from autonomous_media.db.models import Task
from autonomous_media.workers.download import DownloadWorker
from autonomous_media.workers.transcribe import TranscribeWorker
from autonomous_media.workers.topic_extraction import TopicExtractionWorker

def run_test():
    print("=== Testing Phase 1 Core Loop ===")
    
    # 1. Test Download Worker
    download_task = Task(
        id=uuid.uuid4(),
        task_type="download",
        payload={"video_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}, # Short video "Me at the zoo"
        attempts=0,
        max_attempts=3
    )
    
    dl_worker = DownloadWorker()
    try:
        dl_result = dl_worker.run(download_task)
        print("Download successful:", dl_result.summary())
    except Exception as e:
        print("Download failed:", e)
        return

    # 2. Test Transcribe Worker
    transcribe_task = Task(
        id=uuid.uuid4(),
        task_type="transcribe",
        payload={"audio_storage_key": dl_result.storage_key},
        attempts=0,
        max_attempts=3
    )
    
    ts_worker = TranscribeWorker()
    try:
        ts_result = ts_worker.run(transcribe_task)
        print("Transcription successful:", ts_result.summary())
    except Exception as e:
        print("Transcription failed:", e)
        return

    # 3. Test Topic Extraction Worker
    topic_task = Task(
        id=uuid.uuid4(),
        task_type="topic_extraction",
        payload={"transcript_key": ts_result.transcript_key},
        attempts=0,
        max_attempts=3
    )
    
    te_worker = TopicExtractionWorker()
    try:
        te_result = te_worker.run(topic_task)
        print("Topic Extraction successful:", te_result.summary())
    except Exception as e:
        print("Topic Extraction failed:", e)

if __name__ == "__main__":
    run_test()
