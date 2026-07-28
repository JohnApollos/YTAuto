"""
YouTubeClipSource — V1's only ContentSource implementation (spec §11.3).

CRITICAL quota rule (spec §5.1): NEVER use search.list (100 units/call).
Always resolve the channel's uploads playlist ID once via channels.list
(1 unit), then poll playlistItems.list (1 unit/page) for new videos.
"""
from __future__ import annotations

from autonomous_media.sources.base import ContentSource, SourceItem, RawMedia
from autonomous_media.logging import get_logger

logger = get_logger("sources.youtube_clip")


class YouTubeClipSource:
    """
    Implements ContentSource for YouTube channels.

    Args:
        channel_youtube_id: The YouTube channel ID (UCxxxxxx...).
        api_key: YouTube Data API v3 key (or OAuth token for the project).
        since_published_after: ISO 8601 datetime — only return videos newer than this.
    """

    def __init__(self, channel_youtube_id: str, api_key: str, since_published_after: str | None = None):
        self.channel_youtube_id = channel_youtube_id
        self.api_key = api_key
        self.since_published_after = since_published_after
        self._uploads_playlist_id: str | None = None

    def _get_uploads_playlist_id(self) -> str:
        """
        Resolve the channel's uploads playlist ID once and cache it.
        Cost: 1 quota unit (channels.list with part=contentDetails).
        """
        if self._uploads_playlist_id:
            return self._uploads_playlist_id

        # Stub: in real impl, call YouTube Data API v3:
        # GET https://www.googleapis.com/youtube/v3/channels
        #   ?part=contentDetails&id={channel_id}&key={api_key}
        # Then: response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        logger.info(
            "Resolving uploads playlist",
            extra={"trace_id": "discovery", "channel_id": self.channel_youtube_id},
        )
        # STUB: replace with real API call
        self._uploads_playlist_id = f"UU{self.channel_youtube_id[2:]}"
        return self._uploads_playlist_id

    def discover(self) -> list[SourceItem]:
        """
        Poll the channel's uploads playlist for new videos.
        Cost: 1 quota unit per page (playlistItems.list), NOT search.list.
        """
        playlist_id = self._get_uploads_playlist_id()
        logger.info(
            "Polling uploads playlist",
            extra={"trace_id": "discovery", "playlist_id": playlist_id},
        )

        # STUB: replace with real paginated API call to:
        # GET https://www.googleapis.com/youtube/v3/playlistItems
        #   ?part=snippet&playlistId={playlist_id}&maxResults=50&key={api_key}
        # Filter by snippet.publishedAt > self.since_published_after if set
        items: list[SourceItem] = []
        return items

    def fetch(self, item: SourceItem) -> RawMedia:
        """
        Download video and extract audio using yt-dlp.
        Spec §12.2: verify checksum, store in MinIO, create source_videos row.
        SSRF guard: only YouTube URLs are allowed through here (spec §14.5).
        """
        if "youtube.com" not in item.url and "youtu.be" not in item.url:
            raise ValueError(f"SSRF guard: unexpected URL domain in fetch: {item.url}")

        logger.info(
            "Fetching video",
            extra={"trace_id": "acquisition", "video_id": item.external_id},
        )
        # STUB: replace with real yt-dlp download
        # import yt_dlp
        # ydl_opts = {'format': 'bestvideo+bestaudio/best', 'outtmpl': f'/tmp/{item.external_id}.%(ext)s'}
        # with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #     ydl.download([item.url])
        return RawMedia(source_item=item)


# V2 stubs — implement when their roadmap phase begins (spec §11.3)
class AIStorySource:
    """Stub — V2: idea → outline → script → narration → render."""
    def discover(self) -> list[SourceItem]:
        raise NotImplementedError("AIStorySource is a V2 feature")
    def fetch(self, item: SourceItem) -> RawMedia:
        raise NotImplementedError("AIStorySource is a V2 feature")
