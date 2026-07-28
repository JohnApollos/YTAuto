# Autonomous Media

## Technical Specification & System Design

**Version:** 1.4 (V2 Draft)
**Status:** V1 Implemented, V2 Drafting
**Classification:** Internal — Single-Operator System
**Last Updated:** July 28, 2026
**Document Owner:** Project Operator

| Version | Date | Description |
| :--- | :--- | :--- |
| 1.1 | 2026-07-25 | Review pass closed six remaining gaps: a concrete AI evaluation framework with a promotion gate (§18.1), a fully specified Model Runtime strategy |
| 1.2 | 2026-07-28 | Implementation phase adjustments (ADR 0004-0007). |
| 1.3 | 2026-07-28 | Marked as Implemented. Core loop and Dashboard UI complete. |
| 1.4 | 2026-07-28 | Added Phase 6 (Multi-Platform & Asset Generation) draft and open questions. |

*(Refer to the actual technical specification text provided in previous prompts for the complete content of this file.)*

---

## Appendix A: V2 (Phase 6) Upcoming Milestones

With Phase 1-5 (Core Loop & Dashboard) complete, V2 will introduce the following advanced features:

1. **Multi-Platform Syndication**: Expansion from YouTube-only to TikTok and Instagram Reels.
2. **Automated Thumbnail Generation**: Local or Cloud generation of thumbnails (e.g., via Stable Diffusion).
3. **A/B Testing**: Automated rotation of titles and thumbnails based on initial CTR metrics.

### Open Questions (Phase 6 Design)
1. **Compute Contention**: Do we run Stable Diffusion locally (competing with LLaMA/Whisper for VRAM via the `ModelRuntimeManager`), or offload to an external cloud API?
2. **Authentication Flow**: For TikTok and Instagram, do we require an automated background OAuth refresh flow, or will the operator manage tokens manually via the Dashboard?
