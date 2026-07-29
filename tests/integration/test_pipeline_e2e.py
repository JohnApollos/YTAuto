import sys
from unittest.mock import patch, MagicMock
mock_st = MagicMock()
sys.modules["sentence_transformers"] = mock_st
sys.modules["sentence_transformers.SentenceTransformer"] = mock_st.SentenceTransformer

import pytest
import uuid
import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autonomous_media.db.base import Base
from autonomous_media.db.models import (
    Job, Channel, ContentSource, SourceVideo, Transcript, ClipCandidate, Clip, InventoryItem, SystemEvent, Topic, RightsRecord, AnalyticsSnapshot, Model, EvalRun
)
from autonomous_media.workers.intelligence import IntelligenceWorker
from autonomous_media.workers.editing import EditingWorker
from autonomous_media.workers.quality_gate import QualityGateWorker

# Setup clean database engine for integration tests
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")

@pytest.fixture(scope="module")
def db_engine():
    connect_args = {}
    if "sqlite" in DATABASE_URL:
        connect_args["check_same_thread"] = False
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()

@patch("sentence_transformers.SentenceTransformer")
@patch("autonomous_media.db.session.SessionLocal")
@patch("autonomous_media.workers.intelligence.get_object_data")
@patch("autonomous_media.workers.editing.get_object_data")
@patch("autonomous_media.workers.editing.put_object_data")
@patch("autonomous_media.workers.quality_gate.download_file")
@patch("ffmpeg.probe")
@patch("os.path.exists", return_value=True)
def test_pipeline_e2e_flow(
    mock_exists, mock_probe, mock_qg_download, mock_edit_put, mock_edit_get, mock_intel_get, mock_session_local, mock_sentence_transformer, db_session
):
    # Set environments
    os.environ["MODEL_ENV"] = "test"
    os.environ["YOUTUBE_API_ENV"] = "test"

    # Register stub model runtimes dynamically to prevent tests hitting production Vulkan port
    from autonomous_media.runtime.manager import stage_manager, StubModelRuntime
    _stub = StubModelRuntime()
    stage_manager.register("scoring", _stub, fallback=_stub)
    stage_manager.register("title", _stub)
    stage_manager.register("description", _stub)
    stage_manager.register("grounding", _stub)

    # Setup mocked sentence transformer to avoid downloading models in tests
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 768 # Match vector size 768
    mock_sentence_transformer.return_value = mock_model

    # 1. Setup Transcript JSON mock response (35 seconds of words to trigger sliding window & heuristics)
    sentence = "How do we Build high performance systems with Vulkan? That is the question of the day."
    words_text = sentence.split()
    # Add filler words to reach 60 words (36 seconds)
    for i in range(50):
        words_text.append("word")
        
    transcript_words = []
    for idx, w in enumerate(words_text):
        transcript_words.append({
            "word": w,
            "start_ms": idx * 600,
            "end_ms": idx * 600 + 400
        })
        
    mock_intel_get.return_value = json.dumps(transcript_words).encode("utf-8")
    mock_edit_get.return_value = json.dumps(transcript_words).encode("utf-8")

    # 2. Insert DB records
    channel = Channel(
        name="Test Integration Channel",
        slug="test-integration-channel",
        niche="education",
        project_id="google-project-123",
        target_duration_min_s=15,
        target_duration_max_s=45,
        caption_style="default",
        music_profile="default",
        allowed_content_types=["podcast_clip"],
        upload_cadence={"target_per_day": 1}
    )
    db_session.add(channel)
    db_session.commit()

    source = ContentSource(
        channel_id=channel.id,
        type="youtube_channel",
        external_ref="UCtest_int",
        active=True
    )
    db_session.add(source)
    db_session.commit()

    video = SourceVideo(
        content_source_id=source.id,
        external_video_id="video_e2e",
        title="Video E2E Title",
        url="https://youtube.com/watch?v=video_e2e",
        status="downloaded"
    )
    db_session.add(video)
    db_session.commit()

    transcript_id = uuid.uuid4()
    transcript = Transcript(
        id=transcript_id,
        source_video_id=video.id,
        engine="whisper-large-v3-turbo",
        language="en",
        storage_key=f"transcripts/{transcript_id}.json",
        word_count=len(transcript_words)
    )
    db_session.add(transcript)
    db_session.commit()

    # ----------------------------------------------------
    # RUN WORKER 1: IntelligenceWorker
    # ----------------------------------------------------
    session_maker = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    mock_session_local.return_value = session_maker
    intel_worker = IntelligenceWorker(session_maker)
    
    job_intel = Job(
        type="intelligence",
        trace_id="trace-e2e-1",
        channel_id=channel.id,
        payload={"transcript_id": str(transcript_id)}
    )
    db_session.add(job_intel)
    db_session.commit()
    
    intel_worker.run(job_intel)

    # Assert candidate was created
    candidates = db_session.query(ClipCandidate).filter(ClipCandidate.source_video_id == video.id).all()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.start_ms == 0
    assert candidate.end_ms > 30000

    # ----------------------------------------------------
    # RUN WORKER 2: EditingWorker
    # ----------------------------------------------------
    edit_worker = EditingWorker(session_maker)
    job_edit = Job(
        type="editing",
        trace_id="trace-e2e-2",
        channel_id=channel.id,
        payload={"clip_candidate_id": str(candidate.id)}
    )
    db_session.add(job_edit)
    db_session.commit()

    edit_worker.run(job_edit)

    # Assert Clip row created
    clips = db_session.query(Clip).filter(Clip.clip_candidate_id == candidate.id).all()
    assert len(clips) == 1
    clip = clips[0]
    assert clip.status == "rendering"
    assert clip.channel_id == channel.id

    # ----------------------------------------------------
    # RUN WORKER 3: QualityGateWorker
    # ----------------------------------------------------
    # Set mock probe return dict (9:16 vertical video, 30s duration, with audio stream)
    mock_probe.return_value = {
        'streams': [
            {'codec_type': 'video', 'width': 1080, 'height': 1920},
            {'codec_type': 'audio'}
        ],
        'format': {
            'duration': '30.0'
        }
    }

    qg_worker = QualityGateWorker(session_maker)
    job_qg = Job(
        type="quality_gate",
        trace_id="trace-e2e-3",
        channel_id=channel.id,
        payload={"clip_id": str(clip.id)}
    )
    db_session.add(job_qg)
    db_session.commit()

    qg_worker.run(job_qg)

    # Re-fetch clip and verify status
    db_session.refresh(clip)
    assert clip.status == "qc_passed"

    # Verify InventoryItem is created and status="ready"
    inv_items = db_session.query(InventoryItem).filter(InventoryItem.clip_id == clip.id).all()
    assert len(inv_items) == 1
    inv_item = inv_items[0]
    assert inv_item.status == "ready"
    assert inv_item.channel_id == channel.id
