import pytest
from unittest.mock import patch, MagicMock
from autonomous_media.sources.youtube_clip import YouTubeClipSource
from autonomous_media.sources.base import SourceItem
from autonomous_media.exceptions import StageUnrecoverableError, QuotaExceededError
import httpx

def test_get_uploads_playlist_id_success():
    source = YouTubeClipSource(channel_youtube_id="UC12345", api_key="test_key")
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UU12345"
                    }
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    
    with patch("httpx.get", return_value=mock_response) as mock_get:
        playlist_id = source._get_uploads_playlist_id()
        assert playlist_id == "UU12345"
        mock_get.assert_called_once_with(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "contentDetails",
                "id": "UC12345",
                "key": "test_key"
            }
        )

def test_get_uploads_playlist_id_not_found():
    source = YouTubeClipSource(channel_youtube_id="UC12345", api_key="test_key")
    
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}
    mock_response.raise_for_status.return_value = None
    
    with patch("httpx.get", return_value=mock_response):
        with pytest.raises(StageUnrecoverableError) as exc_info:
            source._get_uploads_playlist_id()
        assert "Channel not found" in str(exc_info.value)

def test_get_uploads_playlist_id_quota_exceeded():
    source = YouTubeClipSource(channel_youtube_id="UC12345", api_key="test_key")
    
    # We mock status_code 403 or 429
    response = httpx.Response(403, request=httpx.Request("GET", "https://example.com"))
    mock_err = httpx.HTTPStatusError("Quota Exceeded", request=response.request, response=response)
    
    with patch("httpx.get", side_effect=mock_err):
        with pytest.raises(QuotaExceededError) as exc_info:
            source._get_uploads_playlist_id()
        assert "Quota exceeded" in str(exc_info.value)

def test_discover_success():
    source = YouTubeClipSource(channel_youtube_id="UC12345", api_key="test_key", since_published_after="2026-01-01T00:00:00Z")
    
    # Mock uploads playlist ID resolution
    source._uploads_playlist_id = "UU12345"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid1"},
                    "title": "Video 1",
                    "publishedAt": "2026-01-02T12:00:00Z"
                }
            },
            {
                "snippet": {
                    "resourceId": {"videoId": "vid2"},
                    "title": "Video 2",
                    "publishedAt": "2025-12-31T12:00:00Z" # older than since_published_after
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    
    with patch("httpx.get", return_value=mock_response) as mock_get:
        discovered = source.discover(existing_ids={"vid_existing"})
        # Should stop before video 2 since it is older
        assert len(discovered) == 1
        assert discovered[0].external_id == "vid1"
        assert discovered[0].title == "Video 1"
        assert discovered[0].url == "https://www.youtube.com/watch?v=vid1"
        assert discovered[0].published_at == "2026-01-02T12:00:00Z"

def test_discover_existing_id_stop():
    source = YouTubeClipSource(channel_youtube_id="UC12345", api_key="test_key")
    source._uploads_playlist_id = "UU12345"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid1"},
                    "title": "Video 1",
                    "publishedAt": "2026-01-02T12:00:00Z"
                }
            },
            {
                "snippet": {
                    "resourceId": {"videoId": "vid2"},
                    "title": "Video 2",
                    "publishedAt": "2026-01-01T12:00:00Z"
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    
    with patch("httpx.get", return_value=mock_response):
        # vid2 is already in existing_ids, so pagination should stop at vid2
        discovered = source.discover(existing_ids={"vid2"})
        assert len(discovered) == 1
        assert discovered[0].external_id == "vid1"
