def test_models_importable():
    from autonomous_media.db.models import Job, Channel, ContentSource, SourceVideo
    assert Job is not None
    assert Channel is not None
    assert ContentSource is not None
    assert SourceVideo is not None
