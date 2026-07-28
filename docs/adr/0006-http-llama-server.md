# 6. HTTP llama-server for LLM Inference

Date: 2026-07-28

## Status
Accepted

## Context
In Phase 2, the system needs to invoke the local LLM (`llama.cpp`) to evaluate candidate clips. We need a reliable way to enforce strict JSON output schemas so the scores can be reliably parsed and saved to the database.

## Decision
Instead of invoking the `main` or `llama-cli` binaries as a subprocess and parsing `stdout` (as we did with `whisper.cpp`), we will invoke the `llama-server` binary. The `ModelRuntimeManager` will spin up the server on a local port, and the `EvaluateWorker` will make standard HTTP requests to the `/v1/chat/completions` endpoint, passing `{"type": "json_object"}`.

## Consequences
- **Positive**: We get standard OpenAI-compatible API endpoints locally. This allows us to strictly enforce JSON schema grammars without brittle regex parsing on stdout.
- **Negative**: Adds a slight overhead of managing a local HTTP server lifecycle in the `ModelRuntimeManager` (starting and stopping the background process).
