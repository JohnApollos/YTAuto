import os
import json
import uuid
import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, Transcript, ClipCandidate, Topic
from autonomous_media.storage import get_object_data
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.runtime.manager import stage_manager, InferenceRequest
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.intelligence")

class IntelligenceWorker(Worker):
    job_type = 'intelligence'

    def process(self, session: Session, job: Job) -> JobResult:
        transcript_id = job.payload.get("transcript_id")
        if not transcript_id:
            raise StageUnrecoverableError("Missing transcript_id in job payload")

        transcript = session.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise StageUnrecoverableError(f"Transcript {transcript_id} not found")

        logger.info(
            f"Starting intelligence analysis for transcript {transcript_id}",
            extra={"trace_id": job.trace_id}
        )

        # 1. Fetch transcript JSON from MinIO
        try:
            transcript_bytes = get_object_data("autonomous-media-raw", transcript.storage_key)
            words = json.loads(transcript_bytes.decode("utf-8"))
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to fetch or parse transcript JSON: {e}")

        if not words:
            logger.info("Transcript contains no words. Skipping.", extra={"trace_id": job.trace_id})
            return JobResult()

        # 2. Sliding-window candidate generation
        candidates = self._generate_candidates(words)
        logger.info(
            f"Generated {len(candidates)} raw sliding-window candidates",
            extra={"trace_id": job.trace_id}
        )

        # 3. Heuristic first-pass filter
        passed_candidates = []
        for cand in candidates:
            # Word rate check (min 1.5 words per second)
            duration_s = (cand["end_ms"] - cand["start_ms"]) / 1000.0
            word_count = len(cand["text"].split())
            word_rate = word_count / duration_s if duration_s > 0 else 0
            if word_rate < 1.5:
                continue

            # First sentence check
            if not self._first_sentence_heuristics(cand["text"]):
                continue

            # Heuristic score for ranking
            num_caps = sum(1 for w in cand["text"].split() if w and w[0].isupper())
            heuristic_score = num_caps * 2 + (10 if "?" in cand["text"] else 0)
            
            passed_candidates.append({
                **cand,
                "heuristic_score": heuristic_score
            })

        logger.info(
            f"{len(passed_candidates)} candidates passed heuristic filter",
            extra={"trace_id": job.trace_id}
        )

        if not passed_candidates:
            logger.info("No candidates passed the heuristic filter.", extra={"trace_id": job.trace_id})
            return JobResult()

        # Keep top 15 candidates by heuristic score
        passed_candidates.sort(key=lambda x: x["heuristic_score"], reverse=True)
        top_candidates = passed_candidates[:15]

        # 4. Batched LLM scoring via StageModelManager
        # Load scoring prompt template
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "prompts", "scoring_v3.txt"
        )
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to load scoring prompt template: {e}")

        # Load embedding model for novelty check
        try:
            from sentence_transformers import SentenceTransformer
            # Use 768-dimensional model to match topics.embedding database column
            embed_model = SentenceTransformer("all-mpnet-base-v2")
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to initialize SentenceTransformer: {e}")

        final_candidates = []

        for cand in top_candidates:
            # Format prompt
            prompt = (
                prompt_template
                .replace("{channel_profile_summary}", "Niche: Tech and Startups podcast")
                .replace("{start_ms}", str(cand["start_ms"]))
                .replace("{end_ms}", str(cand["end_ms"]))
                .replace("{candidate_text}", cand["text"])
            )

            # Call local scoring model via StageModelManager
            try:
                inference_res = stage_manager.run_stage("scoring", InferenceRequest(prompt=prompt))
                scores = json.loads(inference_res.text)
            except Exception as e:
                logger.warning(
                    f"LLM scoring failed for candidate window {cand['start_ms']}-{cand['end_ms']}: {e}",
                    extra={"trace_id": job.trace_id}
                )
                continue

            # Compute weighted score
            weighted_score = (
                scores.get("hook_strength", 0) * 1.0 +
                scores.get("emotional_intensity", 0) * 1.0 +
                scores.get("curiosity_gap", 0) * 1.0 +
                scores.get("humor", 0) * 0.7 +
                scores.get("educational_value", 0) * 1.0 +
                scores.get("story_completeness", 0) * 0.8
            )

            # Novelty/dedup check via pgvector
            candidate_embedding = list(embed_model.encode(cand["text"]))
            
            # Query pgvector cosine distance
            # If distance < 0.15, it's a duplicate and we discard it
            is_duplicate = False
            nearest_topic = session.query(Topic).order_by(Topic.embedding.cosine_distance(candidate_embedding)).first()
            if nearest_topic:
                distance = session.scalar(Topic.embedding.cosine_distance(candidate_embedding))
                if distance is not None and distance < 0.15:
                    logger.info(
                        f"Candidate duplicate discarded. Nearest topic distance: {distance:.4f}",
                        extra={"trace_id": job.trace_id}
                    )
                    is_duplicate = True
            
            if is_duplicate:
                continue

            final_candidates.append({
                **cand,
                "scores": scores,
                "weighted_score": weighted_score,
                "embedding": candidate_embedding
            })

        if not final_candidates:
            logger.info("No candidates remained after LLM scoring and novelty filtering.", extra={"trace_id": job.trace_id})
            return JobResult()

        # Sort by weighted score descending
        final_candidates.sort(key=lambda x: x["weighted_score"], reverse=True)
        
        # Keep top 3 candidates (spec selection rule)
        selected_candidates = final_candidates[:3]

        for rank, cand in enumerate(selected_candidates, start=1):
            # Create Topic row for pgvector uniqueness check on future videos
            topic_id = uuid.uuid4()
            # Extract first sentence as label
            sentences = re.split(r'(?<=[.!?])\s+', cand["text"].strip())
            label = sentences[0] if sentences else "Topic"
            topic = Topic(
                id=topic_id,
                label=label[:100], # limit length
                embedding=cand["embedding"],
                created_at=datetime.now(timezone.utc)
            )
            session.add(topic)
            session.flush()

            # Create ClipCandidate row
            clip_cand = ClipCandidate(
                id=uuid.uuid4(),
                source_video_id=transcript.source_video_id,
                topic_id=topic_id,
                start_ms=cand["start_ms"],
                end_ms=cand["end_ms"],
                scores=cand["scores"],
                rank=rank,
                status="selected",
                created_at=datetime.now(timezone.utc)
            )
            session.add(clip_cand)
            session.flush()

            # Enqueue vision job for each selected candidate
            next_job = Job(
                type="vision",
                payload={"clip_candidate_id": str(clip_cand.id)},
                trace_id=job.trace_id,
                channel_id=job.channel_id,
                priority=job.priority,
                attempts=0,
                max_attempts=3
            )
            session.add(next_job)
            session.commit()

            logger.info(
                f"Selected candidate ranked {rank} (score {cand['weighted_score']:.2f}) enqueued for vision stage",
                extra={"trace_id": job.trace_id, "clip_candidate_id": str(clip_cand.id)}
            )

        emit_event(
            event_type="clip.candidates.scored",
            trace_id=job.trace_id,
            payload={
                "transcript_id": str(transcript_id),
                "candidates_scored_count": len(final_candidates),
                "candidates_selected_count": len(selected_candidates)
            }
        )

        return JobResult()

    def _generate_candidates(self, words: list[dict]) -> list[dict]:
        if not words:
            return []
        
        candidates = []
        total_duration_ms = words[-1]['end_ms'] - words[0]['start_ms']
        if total_duration_ms < 30000:
            return []
            
        current_start_ms = words[0]['start_ms']
        end_limit_ms = words[-1]['end_ms']
        
        while current_start_ms + 30000 <= end_limit_ms:
            # Find first word starting at or after current_start_ms
            start_idx = -1
            for idx, w in enumerate(words):
                if w['start_ms'] >= current_start_ms:
                    start_idx = idx
                    break
            if start_idx == -1:
                break
                
            start_w = words[start_idx]
            
            # Find all possible ending words j
            possible_ends = []
            for idx in range(start_idx, len(words)):
                w = words[idx]
                duration = w['end_ms'] - start_w['start_ms']
                if 30000 <= duration <= 90000:
                    possible_ends.append((idx, duration))
                elif duration > 90000:
                    break
                    
            if possible_ends:
                best_idx = -1
                best_score = float('inf')
                
                for idx, duration in possible_ends:
                    word_text = words[idx]['word'].strip()
                    is_boundary = word_text and word_text[-1] in {'.', '?', '!'}
                    
                    # Distance to 60 seconds
                    dist_to_60s = abs(duration - 60000)
                    
                    # Sentence boundary gets a big bonus
                    score = dist_to_60s - (100000 if is_boundary else 0)
                    
                    if score < best_score:
                        best_score = score
                        best_idx = idx
                        
                if best_idx != -1:
                    candidate_words = words[start_idx : best_idx + 1]
                    candidate_text = " ".join(w['word'] for w in candidate_words)
                    candidates.append({
                        "start_ms": start_w['start_ms'],
                        "end_ms": words[best_idx]['end_ms'],
                        "text": candidate_text
                    })
                    
            current_start_ms += 5000
            
        return candidates

    def _first_sentence_heuristics(self, text: str) -> bool:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if not sentences:
            return False
        first_sentence = sentences[0]
        
        # 1. Question check
        has_question = "?" in first_sentence
        
        # 2. Named entity proxy: capitalized words (excluding first word of sentence)
        words = re.findall(r'\b\w+\b', first_sentence)
        has_named_entity = False
        if len(words) > 1:
            for w in words[1:]:
                if w and w[0].isupper():
                    has_named_entity = True
                    break
                    
        # 3. Strong verb check
        strong_verb_keywords = {
            "build", "create", "destroy", "discover", "explore", "reveal", "transform",
            "achieve", "command", "conquer", "launch", "invent", "hack", "predict",
            "warn", "expose", "fight", "kill", "save", "threaten", "succeed", "fail",
            "realize", "remember", "forget", "decide", "choose", "believe", "doubt",
            "wonder", "explain", "prove", "hide", "seek", "steal", "buy", "sell"
        }
        has_strong_verb = any(v in first_sentence.lower() for v in strong_verb_keywords)
        
        return has_question or has_named_entity or has_strong_verb
