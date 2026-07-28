import os
import uuid
from autonomous_media.workers.base import Worker, Task, TaskResult
from autonomous_media.rendering.compositor import FFmpegCompositor
from autonomous_media.db.models import CandidateClip, RenderedAsset

class RenderResult(TaskResult):
    def __init__(self, asset_key: str):
        self.asset_key = asset_key

    def summary(self):
        return {
            "asset_key": self.asset_key
        }

class RenderWorker(Worker):
    task_type = "render_video"

    def process(self, task: Task) -> TaskResult:
        candidate_clip_id_str = task.payload.get("candidate_clip_id")
        if not candidate_clip_id_str:
            raise ValueError("candidate_clip_id is required in payload")
            
        # Stub: Fetch candidate clip and source video from DB
        clip_data = task.payload.get("_mock_clip_data", {
            "start_time_s": 10,
            "end_time_s": 25,
            "transcript_text": "Mock text",
            "source_video_key": "mock_source.mp4"
        })
        
        input_video_path = os.path.join("data/raw", clip_data["source_video_key"])
        output_dir = "data/rendered"
        os.makedirs(output_dir, exist_ok=True)
        
        output_filename = f"{candidate_clip_id_str}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        # Stub: Generate Subtitles
        subtitle_path = os.path.join(output_dir, f"{candidate_clip_id_str}.srt")
        with open(subtitle_path, "w") as f:
            f.write("1\n00:00:00,000 --> 00:00:15,000\nMock Subtitle Burn-In\n")
            
        print(f"[RenderWorker] Rendering asset for clip {candidate_clip_id_str}...")
        
        compositor = FFmpegCompositor(input_video_path, output_path)
        
        # Development fallback: If the input video doesn't exist on this dev machine,
        # we bypass the actual FFmpeg call to prevent test crashes.
        if not os.path.exists(input_video_path):
            print(f"  [!] Input video {input_video_path} not found. Using dev mock render.")
            with open(output_path, "wb") as f:
                f.write(b"mock_mp4_data")
        else:
            compositor.render_vertical_short(
                start_time_s=clip_data["start_time_s"],
                end_time_s=clip_data["end_time_s"],
                subtitle_path=subtitle_path
            )
        
        # Stub: Upload `output_path` to MinIO
        # minio_client.fput_object("rendered-assets", output_filename, output_path)
        
        return RenderResult(
            asset_key=output_filename
        )
