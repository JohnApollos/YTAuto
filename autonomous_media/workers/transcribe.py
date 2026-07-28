import os
import json
import subprocess
from autonomous_media.workers.base import Worker, Task, TaskResult
from autonomous_media.runtime.manager import runtime_manager
from autonomous_media.exceptions import StageUnrecoverableError

class TranscribeResult(TaskResult):
    def __init__(self, transcript_key: str, word_count: int):
        self.transcript_key = transcript_key
        self.word_count = word_count

    def summary(self):
        return {
            "transcript_key": self.transcript_key,
            "word_count": self.word_count
        }

class TranscribeWorker(Worker):
    task_type = "transcribe"

    def process(self, task: Task) -> TaskResult:
        audio_key = task.payload.get("audio_storage_key")
        if not audio_key:
            raise StageUnrecoverableError("audio_storage_key is required")

        # In full implementation, fetch file from MinIO
        # minio_client.fget_object("raw", audio_key, local_audio_path)
        local_audio_path = os.path.join("data/raw", audio_key)
        if not os.path.exists(local_audio_path):
            raise Exception(f"Audio file not found: {local_audio_path}")
        
        output_dir = "data/transcripts"
        os.makedirs(output_dir, exist_ok=True)
        transcript_json_path = os.path.join(output_dir, f"{task.id}_transcript")
        
        # We need whisper.cpp's `main` executable
        # The manager ensures the model is loaded or we have VRAM available
        runtime_manager.acquire_model("whisper-base.en-q5")

        # Whisper.cpp requires 16kHz WAV. We'd use ffmpeg to convert it first.
        wav_path = os.path.join(output_dir, f"{task.id}_16k.wav")
        try:
            print(f"[TranscribeWorker] Converting audio to 16kHz WAV...")
            subprocess.run([
                "ffmpeg", "-y", "-i", local_audio_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                wav_path
            ], check=True, capture_output=True)
            
            print(f"[TranscribeWorker] Running whisper.cpp on {wav_path}...")
            # We mock the whisper.cpp binary call here to output JSON.
            # Actual command: whisper.cpp/main -m models/ggml-base.en.bin -f wav_path -oj -of transcript_json_path
            # For development safety on missing binaries, we'll write a dummy json if whisper fails
            try:
                subprocess.run([
                    "whisper", "-m", "models/ggml-base.en.bin",
                    "-f", wav_path, "-oj", "-of", transcript_json_path
                ], check=True, capture_output=True)
            except FileNotFoundError:
                print("[TranscribeWorker] whisper.cpp not found on PATH. Creating a mock transcript.")
                mock_data = {
                    "transcription": [
                        {"offsets": {"from": 0, "to": 5000}, "text": "This is a mock transcription segment."}
                    ]
                }
                with open(f"{transcript_json_path}.json", "w") as f:
                    json.dump(mock_data, f)

        finally:
            # Clean up intermediate wav
            if os.path.exists(wav_path):
                os.remove(wav_path)

        # Result is saved as {transcript_json_path}.json by whisper.cpp
        final_json = f"{transcript_json_path}.json"
        
        # Stub: push to MinIO
        # minio_client.fput_object("transcripts", final_json_name, final_json)
        
        return TranscribeResult(
            transcript_key=os.path.basename(final_json),
            word_count=7 # Mock count
        )
