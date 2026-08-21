"""
scripts/batch_re_render_today.py

Re-processes and re-renders all clips generated today with the updated
animated subtitle engine (Arial Black, 118% scale-bounce pop, yellow karaoke, shadow).
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from autonomous_media.db.session import SessionLocal
from autonomous_media.db.models import Clip, ClipCandidate, SourcePost, Job, InventoryItem
from autonomous_media.workers.editing import EditingWorker
from autonomous_media.workers.rendering import RenderingWorker
from autonomous_media.workers.quality_gate import QualityGateWorker
from autonomous_media.workers.publishing import PublishingWorker

def run_batch_re_render():
    today_start = datetime(2026, 8, 18, 0, 0, 0, tzinfo=timezone.utc)
    
    with SessionLocal() as session:
        # Find all distinct clip candidates from today
        candidates = (
            session.query(ClipCandidate)
            .filter(ClipCandidate.created_at >= today_start)
            .all()
        )
        # Find all distinct source posts from today
        posts = (
            session.query(SourcePost)
            .filter(SourcePost.submitted_at >= today_start)
            .all()
        )

        print(f"Found {len(candidates)} podcast candidates and {len(posts)} Reddit stories to re-render.")
        
        # 1. Process Podcast Candidates
        for idx, candidate in enumerate(candidates, 1):
            print(f"\n[{idx}/{len(candidates)}] Re-rendering Podcast Candidate {candidate.id}...")
            try:
                # Regenerate subtitles
                job_edit = Job(type='editing', payload={'clip_candidate_id': str(candidate.id)}, trace_id=f'batch-re-edit-{candidate.id}')
                EditingWorker(session_maker=SessionLocal).process(session, job_edit)
                
                # Fetch new clip
                new_clip = session.query(Clip).filter(Clip.clip_candidate_id == candidate.id).order_by(Clip.created_at.desc()).first()
                if not new_clip:
                    print("  Failed to create new clip")
                    continue
                
                # Render
                job_render = Job(type='rendering', payload={'clip_id': str(new_clip.id)}, trace_id=f'batch-re-render-{candidate.id}')
                RenderingWorker(session_maker=SessionLocal).process(session, job_render)
                
                # Quality gate & Publish
                job_qg = Job(type='quality_gate', payload={'clip_id': str(new_clip.id)}, trace_id=f'batch-re-qg-{candidate.id}')
                QualityGateWorker(session_maker=SessionLocal).process(session, job_qg)
                
                inv = session.query(InventoryItem).filter(InventoryItem.clip_id == new_clip.id).first()
                if inv:
                    job_pub = Job(type='publishing', payload={'inventory_item_id': str(inv.id)}, trace_id=f'batch-re-pub-{candidate.id}')
                    PublishingWorker(session_maker=SessionLocal).process(session, job_pub)
                print(f"  Podcast Candidate {candidate.id} re-rendered and published successfully!")
            except Exception as e:
                print(f"  Error re-rendering candidate {candidate.id}: {e}")

        # 2. Process Reddit Story Posts
        for idx, post in enumerate(posts, 1):
            print(f"\n[{idx}/{len(posts)}] Re-rendering Reddit Story Post {post.id}...")
            try:
                # Regenerate subtitles
                job_edit = Job(type='editing', payload={'source_post_id': str(post.id)}, trace_id=f'batch-re-edit-{post.id}')
                EditingWorker(session_maker=SessionLocal).process(session, job_edit)
                
                # Fetch new clip
                new_clip = session.query(Clip).filter(Clip.source_post_id == post.id).order_by(Clip.created_at.desc()).first()
                if not new_clip:
                    print("  Failed to create new clip")
                    continue
                
                # Render
                job_render = Job(type='rendering', payload={'clip_id': str(new_clip.id)}, trace_id=f'batch-re-render-{post.id}')
                RenderingWorker(session_maker=SessionLocal).process(session, job_render)
                
                # Quality gate & Publish
                job_qg = Job(type='quality_gate', payload={'clip_id': str(new_clip.id)}, trace_id=f'batch-re-qg-{post.id}')
                QualityGateWorker(session_maker=SessionLocal).process(session, job_qg)
                
                inv = session.query(InventoryItem).filter(InventoryItem.clip_id == new_clip.id).first()
                if inv:
                    job_pub = Job(type='publishing', payload={'inventory_item_id': str(inv.id)}, trace_id=f'batch-re-pub-{post.id}')
                    PublishingWorker(session_maker=SessionLocal).process(session, job_pub)
                print(f"  Reddit Story Post {post.id} re-rendered and published successfully!")
            except Exception as e:
                print(f"  Error re-rendering story {post.id}: {e}")

        print("\nAll batch re-renders finished!")

if __name__ == "__main__":
    run_batch_re_render()
