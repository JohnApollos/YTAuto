# Autonomous Media — Developer Guide

**Companion to:** `autonomous-media-technical-specification.md` (v1.1)
**Purpose:** the specification defines *what* the system does and *why*; this document is *how you actually build it*, in what order, with what conventions.
**Audience:** whoever is writing the code — which, for V1, is one person.

## Troubleshooting & Known Constraints

- **Vulkan / ROCm dependencies**: You must have the correct AMD drivers installed. If Whisper falls back to CPU, it will take 50x longer. Check the `ModelRuntimeManager` logs.
- **Quota Exhaustion**: The YouTube Data API v3 enforces a 10,000 unit/day limit (approx 6 video uploads). When the `PublishWorker` encounters a 403 or 429 Quota Exhausted error from Google, it will catch the `QuotaExhaustedError` and mark the task status as `deferred`. The system scheduler will automatically retry `deferred` tasks every 24 hours until the quota resets, ensuring autonomous operation over long weekends without requiring manual error clearance.

## Phase 6 (V2) Upcoming Work & Open Questions

As we transition into **Phase 6: Multi-Platform Distribution**, developers should consider the following open architectural questions:

1. **VRAM Constraints (Stable Diffusion)**: If thumbnail generation is kept local, the `ModelRuntimeManager` must be updated to track a third VRAM-heavy model. Is the baseline 8GB/16GB VRAM constraint still viable, or should we mandate a cloud API for thumbnails?
2. **OAuth Architectures**: Expanding to TikTok and Instagram will require generalized, multi-tenant capable OAuth flows. Developers will need to refactor the `PublishWorker` to accept generalized credentials rather than hardcoding Google APIs.
