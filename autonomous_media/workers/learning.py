from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, AnalyticsSnapshot, InventoryItem, Clip, ClipCandidate, Channel
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.learning")

SCORE_TO_WEIGHT = {
    "hook_strength": "hook",
    "emotional_intensity": "emotion",
    "curiosity_gap": "curiosity",
    "humor": "humor",
    "educational_value": "educational",
    "story_completeness": "story_completeness"
}

class LearningWorker(Worker):
    job_type = 'learning'

    def process(self, session: Session, job: Job) -> JobResult:
        snapshot_id = job.payload.get("analytics_snapshot_id")
        if not snapshot_id:
            raise StageUnrecoverableError("Missing analytics_snapshot_id in job payload")

        snapshot = session.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.id == snapshot_id).first()
        if not snapshot:
            raise StageUnrecoverableError(f"AnalyticsSnapshot {snapshot_id} not found")

        inventory_item = session.query(InventoryItem).filter(InventoryItem.id == snapshot.inventory_item_id).first()
        if not inventory_item:
            raise StageUnrecoverableError(f"InventoryItem {snapshot.inventory_item_id} not found")

        clip = session.query(Clip).filter(Clip.id == inventory_item.clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {inventory_item.clip_id} not found")

        clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
        if not clip_candidate:
            raise StageUnrecoverableError(f"ClipCandidate {clip.clip_candidate_id} not found")

        channel = session.query(Channel).filter(Channel.id == clip.channel_id).first()
        if not channel:
            raise StageUnrecoverableError(f"Channel {clip.channel_id} not found")

        logger.info(
            f"Starting reinforcement learning pass for Channel {channel.id} using snapshot {snapshot_id}",
            extra={"trace_id": job.trace_id}
        )

        # 1. Identify the highest-scoring dimension of this clip
        candidate_scores = clip_candidate.scores or {}
        valid_scores = {k: v for k, v in candidate_scores.items() if k in SCORE_TO_WEIGHT and isinstance(v, (int, float))}

        if not valid_scores:
            logger.info("ClipCandidate has no valid dimension scores to learn from. Skipping.", extra={"trace_id": job.trace_id})
            return JobResult()

        highest_score_key = max(valid_scores, key=valid_scores.get)
        target_weight_name = SCORE_TO_WEIGHT[highest_score_key]

        # 2. Get current weights from channel branding (defaulting to 1.0)
        branding = dict(channel.branding or {})
        weights = dict(branding.get("scoring_weights", {
            "hook": 1.0,
            "emotion": 1.0,
            "curiosity": 1.0,
            "humor": 0.7,
            "educational": 1.0,
            "story_completeness": 0.8
        }))

        current_weight = weights.get(target_weight_name, 1.0)
        old_weight = current_weight

        # 3. Compute reinforcement adjustment
        views = snapshot.views or 0
        adjustment = 0.0

        if views >= 1000:
            # Positive reinforcement: increment the weight by +0.05
            adjustment = 0.05
            new_weight = min(2.0, current_weight + adjustment)
        elif views <= 100:
            # Negative reinforcement: decrement the weight by -0.05
            adjustment = -0.05
            new_weight = max(0.2, current_weight + adjustment)
        else:
            # Neutral zone: no change
            new_weight = current_weight

        if new_weight != old_weight:
            weights[target_weight_name] = round(new_weight, 4)
            branding["scoring_weights"] = weights
            
            # Reassign branding to trigger SQLAlchemy JSON mutation tracking
            channel.branding = branding
            session.commit()

            # Emit event
            emit_event(
                event_type="learning.weights.updated",
                trace_id=job.trace_id,
                payload={
                    "channel_id": str(channel.id),
                    "target_weight_name": target_weight_name,
                    "old_weight": old_weight,
                    "new_weight": new_weight,
                    "views": views
                }
            )

            logger.info(
                f"Reinforcement learning: Adjusted weight '{target_weight_name}' from {old_weight} to {new_weight} (views: {views})",
                extra={"trace_id": job.trace_id}
            )
        else:
            logger.info(
                f"Scoring weight '{target_weight_name}' remained unchanged at {old_weight} (views: {views})",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()
