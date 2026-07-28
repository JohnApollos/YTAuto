# 5. Model Runtime Manager for VRAM Residency

Date: 2026-07-28

## Status
Accepted

## Context
The target hardware (RX 580) has severe memory constraints (8GB VRAM, 16GB System RAM). During Phase 1 implementation, the system needs to run both `whisper.cpp` (for transcription) and `llama.cpp` (for topic extraction and scoring). Loading both models into memory simultaneously will cause Out-Of-Memory (OOM) crashes.

## Decision
We implemented a `ModelRuntimeManager` with a `swap` residency mode. Before any worker executes a subprocess that requires a local AI model, it must request a lock from the `ModelRuntimeManager` for that specific model. 

## Consequences
- **Positive**: Guarantees that only one large model is resident in memory at any given time, preventing OOM crashes and ensuring stable operation on constrained hardware.
- **Negative**: Introduces a global lock bottleneck. Workers must wait for the current model to be unloaded and the new model to be loaded into VRAM, increasing latency between stage transitions. Given this is a background asynchronous system, this latency is an acceptable tradeoff for stability.
