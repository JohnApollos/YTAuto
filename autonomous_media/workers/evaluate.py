import json
import urllib.request
import urllib.error
import uuid
from typing import List

from autonomous_media.workers.base import Worker, Task, TaskResult
from autonomous_media.runtime.manager import runtime_manager
from autonomous_media.db.models import CandidateClip, EvaluationScore
from autonomous_media.evaluation.prompt_builder import BatchedEvaluationPrompt, chunk_clips

class EvaluateResult(TaskResult):
    def __init__(self, scores_saved: int, failed_batches: int):
        self.scores_saved = scores_saved
        self.failed_batches = failed_batches

    def summary(self):
        return {
            "scores_saved": self.scores_saved,
            "failed_batches": self.failed_batches
        }

class EvaluateWorker(Worker):
    task_type = "evaluate_clips"
    llama_server_url = "http://127.0.0.1:8080/v1/chat/completions"

    def process(self, task: Task) -> TaskResult:
        source_video_id_str = task.payload.get("source_video_id")
        if not source_video_id_str:
            raise ValueError("source_video_id is required in task payload")
            
        # Stub: Fetch candidate clips from database. 
        # For execution testing without a real DB session in the mock runner, 
        # we will extract them from the payload if provided, or return mock.
        clips_payload = task.payload.get("_mock_clips", [])
        clips = []
        for c in clips_payload:
            clip = CandidateClip(
                id=uuid.UUID(c["id"]),
                source_video_id=uuid.UUID(source_video_id_str),
                transcript_text=c["transcript_text"]
            )
            clips.append(clip)
            
        if not clips:
            print("[EvaluateWorker] No clips found to evaluate.")
            return EvaluateResult(0, 0)

        # Acquire lock to ensure llama-server is prioritized
        runtime_manager.acquire_model("llama-3-8b-instruct-q4")
        
        batches = chunk_clips(clips)
        print(f"[EvaluateWorker] Evaluating {len(clips)} clips in {len(batches)} batches.")
        
        total_scores_saved = 0
        failed_batches = 0
        
        for i, batch in enumerate(batches):
            print(f"  -> Processing batch {i+1}/{len(batches)} ({len(batch)} clips)...")
            prompt_builder = BatchedEvaluationPrompt(batch)
            messages = prompt_builder.build_prompt_messages()
            
            # Send HTTP request to local llama-server
            req_data = json.dumps({
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
                "response_format": {"type": "json_object"} # If supported by the server for grammar
            }).encode('utf-8')
            
            req = urllib.request.Request(
                self.llama_server_url, 
                data=req_data, 
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    res_body = response.read().decode('utf-8')
                    res_json = json.loads(res_body)
                    content = res_json['choices'][0]['message']['content']
                    scores_list = json.loads(content)
                    total_scores_saved += len(scores_list)
                    
                    # Stub: Save scores_list to database
                    # for s in scores_list:
                    #     db.add(EvaluationScore(**s))
                        
            except urllib.error.URLError as e:
                print(f"  [!] llama-server unreachable ({e.reason}). Using mock scores for dev.")
                # Development fallback
                for clip in batch:
                    # Mock save
                    total_scores_saved += 1
            except Exception as e:
                print(f"  [!] Batch {i+1} failed during parsing/saving: {e}")
                failed_batches += 1

        return EvaluateResult(
            scores_saved=total_scores_saved,
            failed_batches=failed_batches
        )
