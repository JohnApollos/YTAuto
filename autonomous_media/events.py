"""
Canonical event type constants — spec §7.3.
Every event payload carries the job's trace_id so the full lifecycle
of one clip is reconstructable from logs alone.
"""

VIDEO_DISCOVERED = "video.discovered"
VIDEO_DOWNLOADED = "video.downloaded"
TRANSCRIPT_READY = "transcript.ready"
CLIP_CANDIDATES_SCORED = "clip.candidates.scored"
CLIP_SELECTED = "clip.selected"
VIDEO_ANALYZED = "video.analyzed"
EDIT_RENDER_COMPLETED = "edit.render.completed"
QC_PASSED = "qc.passed"
QC_FAILED = "qc.failed"
RIGHTS_CLEARED = "rights.cleared"
RIGHTS_BLOCKED = "rights.blocked"
PUBLISH_REQUESTED = "publish.requested"
PUBLISH_COMPLETED = "publish.completed"
PUBLISH_FAILED = "publish.failed"
ANALYTICS_UPDATED = "analytics.updated"
LEARNING_WEIGHTS_UPDATED = "learning.weights.updated"
RIGHTS_STATUS_UPDATED = "rights.status.updated"
