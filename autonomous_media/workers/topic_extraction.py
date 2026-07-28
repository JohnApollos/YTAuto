import os
import json
from autonomous_media.workers.base import Worker, Task, TaskResult
from autonomous_media.runtime.manager import runtime_manager
from autonomous_media.exceptions import StageUnrecoverableError

class TopicExtractionResult(TaskResult):
    def __init__(self, topic_count: int):
        self.topic_count = topic_count

    def summary(self):
        return {
            "topic_count": self.topic_count
        }

class TopicExtractionWorker(Worker):
    task_type = "topic_extraction"

    def process(self, task: Task) -> TaskResult:
        transcript_key = task.payload.get("transcript_key")
        if not transcript_key:
            raise StageUnrecoverableError("transcript_key is required")

        # In full implementation, fetch file from MinIO
        local_transcript = os.path.join("data/transcripts", transcript_key)
        if not os.path.exists(local_transcript):
            raise Exception(f"Transcript file not found: {local_transcript}")
        
        with open(local_transcript, "r") as f:
            transcript_data = json.load(f)

        # Acquire LLM model
        runtime_manager.acquire_model("llama-3-8b-instruct-q4")
        
        print(f"[TopicExtractionWorker] Extracting topics using local LLM for {transcript_key}...")
        
        # Stub: We would use httpx to call llama-server's /completion endpoint here
        # with the transcript segments to identify hooks and topics.
        
        # Stub: insert into pgvector `topics` table
        # db.add(Topic(label="Mock Topic", embedding=[0.0]*768))

        return TopicExtractionResult(
            topic_count=1
        )
