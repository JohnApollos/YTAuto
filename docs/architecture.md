# System Architecture

This document provides a high-level overview of the Autonomous Media system architecture. For the reasoning behind these decisions, please refer to the `docs/adr/` directory.

## Core Design Principles

1. **Modular Monolith**: The system is contained in a single repository and runs as a unified Python/FastAPI backend, eliminating the operational overhead of microservices (ADR 0001).
2. **Hardware-Aware constraints**: The system is designed for a single consumer PC (RX 580, 16GB RAM). Heavy computational models are swapped in and out of memory rather than running concurrently.
3. **Idempotent Workflows**: The background processing is strictly modeled as `Workflow -> Stage -> Task` to ensure that failures (e.g. out of memory crashes) only require restarting the atomic task, not the entire pipeline (ADR 0004).

## System Components

### 1. Database & State (PostgreSQL)
- Serves as the single source of truth for Channels, Candidate Clips, Evaluation Scores, and Workflow states.
- Utilizes `pgvector` for storing semantic topic embeddings.

### 2. File Storage (MinIO / S3)
- Handles raw downloaded video/audio.
- Stores `.json` transcripts, `.srt` subtitle files, and the final `.mp4` vertical renders.

### 3. Model Runtime Manager
- An exclusive locking mechanism (ADR 0005) that ensures only one large AI model (Whisper or LLaMA) is resident in VRAM at any given time.
- Interfaces with local executables or local HTTP servers (ADR 0006) to enforce strict structured outputs from the LLMs.

### 4. Background Workers
Workers operate on isolated `Task` payloads and transition the Workflow State upon completion:
- **`DownloadWorker`**: Interfaces with `yt-dlp`.
- **`TranscribeWorker`**: Interfaces with `whisper.cpp` (Vulkan) for fast local audio transcription.
- **`TopicExtractionWorker`**: Initial pass to map transcripts to hooks and topics.
- **`EvaluateWorker`**: Interfaces with `llama-server` to perform Batched Scoring (ADR 0003) on potential viral clips.
- **`RenderWorker`**: Uses `ffmpeg-python` (ADR 0007) to construct complex filtergraphs, overlay captions, blur backgrounds, and render the final MP4.
- **`PublishWorker`** (Upcoming): Handles OAuth flow and quota-aware YouTube API uploading.
