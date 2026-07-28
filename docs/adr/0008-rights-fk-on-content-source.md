# ADR 0008 — Rights FK on `content_source_id`, Not `source_video_id`

**Date:** 2026-07-28
**Status:** Accepted

## Context

During the spec v1.2 compliance audit, the `rights_records` table was found to have its foreign key on `source_video_id`. This meant that every individual video downloaded from a source channel would need a separate rights record. An operator would need to repeatedly clear rights for hundreds of videos from the same source.

The question: should rights be tracked per-video, or per-source?

## Decision

Rights are tracked **per `content_source`**, not per `source_video`. The `rights_records.content_source_id` FK references the `content_sources` table.

A `content_source` represents an entire YouTube channel, RSS feed, or other content origin. The operator negotiates rights (or determines they are not needed) at the source level, not the individual video level. A channel that is `licensed` remains `licensed` for all videos discovered from it until explicitly changed.

The status values are: `owned`, `licensed`, `permission_granted`, `unknown`, `denied`.

`fair_use_asserted` is deliberately **not** a valid status. Fair use is a legal determination that must go through a manual override path with legal review — it cannot be set programmatically.

## Consequences

**Positive:**
- Rights management is practical: one decision per source, not one per video.
- The rights gate check (`RightsGate.is_cleared(content_source_id)`) is a single lookup before the publish queue — not a lookup chain from video → source → rights.
- Every status change is audit-logged to `system_events` with `reviewed_by` and `evidence_ref` — the system is defensible to a platform rights dispute.
- `expires_at` field supports time-limited licenses (e.g., a 12-month permission letter).

**Negative:**
- If a source contains mixed-rights content (e.g., 90% owned, 10% third-party footage), the system cannot make that distinction automatically. The operator must either split the content into separate `content_sources` or handle the exceptions via the manual review path.
- This is a known limitation for V1. Multi-granularity rights tracking is a V2 consideration.
