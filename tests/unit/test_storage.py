import pytest
from unittest.mock import patch, MagicMock
from autonomous_media.storage import ensure_all_buckets, ensure_bucket

def test_ensure_bucket_exists():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    
    with patch("autonomous_media.storage.get_minio_client", return_value=mock_client):
        ensure_bucket("test-bucket")
        mock_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_client.make_bucket.assert_not_called()

def test_ensure_bucket_not_exists():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    
    with patch("autonomous_media.storage.get_minio_client", return_value=mock_client):
        ensure_bucket("test-bucket")
        mock_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_client.make_bucket.assert_called_once_with("test-bucket")

def test_ensure_all_buckets():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    
    with patch("autonomous_media.storage.get_minio_client", return_value=mock_client):
        ensure_all_buckets()
        assert mock_client.bucket_exists.call_count == 4
        assert mock_client.make_bucket.call_count == 4
        mock_client.make_bucket.assert_any_call("autonomous-media-raw")
        mock_client.make_bucket.assert_any_call("autonomous-media-transcripts")
        mock_client.make_bucket.assert_any_call("autonomous-media-renders")
        mock_client.make_bucket.assert_any_call("autonomous-media-branding")
