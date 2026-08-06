import httpx
from autonomous_media.sources.base import ContentSource, SourceItem, RawMedia
from autonomous_media.logging import get_logger
from autonomous_media.exceptions import StageUnrecoverableError, QuotaExceededError

logger = get_logger("sources.youtube_clip")


import re

def parse_iso_duration(duration_str: str) -> int:
    """Parses ISO 8601 duration string (e.g., PT1H2M30S, PT45S) into total seconds."""
    if not duration_str:
        return 0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


class YouTubeClipSource:
    """
    Implements ContentSource for YouTube channels.

    Args:
        channel_youtube_id: The YouTube channel ID (UCxxxxxx...).
        api_key: YouTube Data API v3 key (or OAuth token for the project).
        since_published_after: ISO 8601 datetime — only return videos newer than this.
        max_new_items: Max number of new long-form videos to discover per poll pass.
        min_duration_s: Minimum video duration in seconds (default 120s) to filter out YouTube Shorts.
    """

    def __init__(
        self,
        channel_youtube_id: str,
        api_key: str,
        since_published_after: str | None = None,
        max_new_items: int = 1,
        min_duration_s: int = 120,
    ):
        self.channel_youtube_id = channel_youtube_id
        self.api_key = api_key
        self.since_published_after = since_published_after
        self.max_new_items = max_new_items
        self.min_duration_s = min_duration_s
        self._uploads_playlist_id: str | None = None

    def _fetch_video_durations(self, video_ids: list[str]) -> dict[str, int]:
        """Fetch duration in seconds for a list of video IDs using videos.list API."""
        if not video_ids:
            return {}
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "contentDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        try:
            resp = httpx.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            durations = {}
            for item in data.get("items", []):
                vid = item.get("id")
                dur_str = item.get("contentDetails", {}).get("duration", "")
                durations[vid] = parse_iso_duration(dur_str)
            return durations
        except Exception as e:
            logger.warning(f"Failed to fetch video durations: {e}")
            return {}

    def _get_uploads_playlist_id(self) -> str:
        """
        Resolve the channel's uploads playlist ID once and cache it.
        Cost: 1 quota unit (channels.list with part=contentDetails).
        """
        if self._uploads_playlist_id:
            return self._uploads_playlist_id

        logger.info(
            "Resolving uploads playlist",
            extra={"trace_id": "discovery", "channel_id": self.channel_youtube_id},
        )
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "contentDetails",
            "id": self.channel_youtube_id,
            "key": self.api_key,
        }
        try:
            resp = httpx.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("items"):
                raise StageUnrecoverableError(f"Channel not found or no contentDetails items: {self.channel_youtube_id}")
            self._uploads_playlist_id = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            return self._uploads_playlist_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                raise QuotaExceededError(f"YouTube Quota exceeded or auth error resolving channel uploads: {e}")
            raise StageUnrecoverableError(f"HTTP error resolving uploads playlist: {e}")
        except Exception as e:
            if isinstance(e, (StageUnrecoverableError, QuotaExceededError)):
                raise e
            raise StageUnrecoverableError(f"Failed to resolve uploads playlist: {e}")

    def discover(self, existing_ids: set[str] | None = None) -> list[SourceItem]:
        """
        Poll the channel's uploads playlist for new videos.
        Cost: 1 quota unit per page (playlistItems.list), NOT search.list.
        """
        playlist_id = self._get_uploads_playlist_id()
        logger.info(
            "Polling uploads playlist",
            extra={"trace_id": "discovery", "playlist_id": playlist_id},
        )

        existing_ids = existing_ids or set()
        items: list[SourceItem] = []
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": self.api_key,
        }

        next_page_token = None
        while True:
            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                resp = httpx.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 429):
                    raise QuotaExceededError(f"YouTube Quota exceeded or auth error fetching playlist items: {e}")
                raise StageUnrecoverableError(f"HTTP error polling playlist: {e}")
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to poll playlist items: {e}")

            playlist_items = data.get("items", [])
            if not playlist_items:
                break

            stop_pagination = False
            candidate_batch = []
            for item_data in playlist_items:
                snippet = item_data.get("snippet", {})
                resource_id = snippet.get("resourceId", {})
                video_id = resource_id.get("videoId")
                if not video_id:
                    continue

                # Check if we already have this video
                if video_id in existing_ids:
                    stop_pagination = True
                    break

                published_at = snippet.get("publishedAt")

                # If since_published_after is set, check it
                if self.since_published_after and published_at:
                    if published_at < self.since_published_after:
                        stop_pagination = True
                        break

                title = snippet.get("title", "")
                
                # Check for explicit shorts hashtags in title
                if "#shorts" in title.lower() or "#short" in title.lower():
                    logger.info(
                        f"Skipping video '{title}' ({video_id}) — hashtag indicates YouTube Short",
                        extra={"trace_id": "discovery"}
                    )
                    continue

                candidate_batch.append({
                    "video_id": video_id,
                    "title": title,
                    "published_at": published_at
                })

            if candidate_batch:
                # Fetch video durations to filter out YouTube Shorts (duration < min_duration_s)
                batch_ids = [c["video_id"] for c in candidate_batch]
                durations = self._fetch_video_durations(batch_ids)

                for cand in candidate_batch:
                    vid = cand["video_id"]
                    dur_s = durations.get(vid, 9999)  # default high if lookup fails
                    if dur_s > 0 and dur_s < self.min_duration_s:
                        logger.info(
                            f"Skipping video '{cand['title']}' ({vid}) — duration ({dur_s}s) below min threshold ({self.min_duration_s}s), presumed YouTube Short",
                            extra={"trace_id": "discovery"}
                        )
                        continue

                    video_url = f"https://www.youtube.com/watch?v={vid}"
                    items.append(SourceItem(
                        external_id=vid,
                        title=cand["title"],
                        url=video_url,
                        published_at=cand["published_at"]
                    ))

                    if len(items) >= getattr(self, "max_new_items", 1):
                        stop_pagination = True
                        break

            if stop_pagination:
                break

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

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
        # Note: Actual download logic is handled in AcquisitionWorker using yt-dlp.
        # This fetch method acts as a helper to initiate the process.
        return RawMedia(source_item=item)


# V2 stubs — implement when their roadmap phase begins (spec §11.3)
class AIStorySource:
    """Stub — V2: idea → outline → script → narration → render."""
    def discover(self) -> list[SourceItem]:
        raise NotImplementedError("AIStorySource is a V2 feature")
    def fetch(self, item: SourceItem) -> RawMedia:
        raise NotImplementedError("AIStorySource is a V2 feature")

