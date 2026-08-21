"""
autonomous_media/sources/reddit_story.py

Automated Reddit Stories Acquisition Source.
Polls top storytelling subreddits, filters for virality, quality, and advertiser safety,
and returns structured SourceItems ready for narration, editing, and rendering.
"""

from __future__ import annotations

import re
import requests
from dataclasses import dataclass, field
from autonomous_media.sources.base import SourceItem
from autonomous_media.config import settings
from autonomous_media.logging import get_logger

logger = get_logger("sources.reddit_story")

CURATED_SUBREDDITS = [
    "AmItheAsshole",
    "relationship_advice",
    "tifu",
    "TrueOffMyChest",
    "confession",
    "pettyrevenge",
    "maliciouscompliance",
    "AskReddit",
]

BLOCKED_KEYWORDS = {
    "suicide", "kill myself", "pedophile", "nazi", "terrorist",
    "child abuse", "sexual assault", "rape", "murdered", "slaughtered"
}


def clean_reddit_story_text(raw_text: str) -> str:
    """Strips Reddit markdown artifacts, edits, updates, links, and throwaway disclaimers."""
    text = raw_text.strip()
    # Remove markdown links [text](http...)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove raw URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove EDIT / UPDATE sections at the end
    text = re.sub(r'(?i)\n\s*(?:EDIT|UPDATE|TL;?DR|UPDATE \d+):.*$', '', text, flags=re.DOTALL)
    # Remove throwaway account disclaimers
    text = re.sub(r'(?i)^.*throwaway account.*?\n+', '', text)
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@dataclass
class RedditStorySource:
    subreddits: list[str] = field(default_factory=lambda: list(CURATED_SUBREDDITS))
    client_id: str | None = None
    client_secret: str | None = None
    user_agent: str = "YTAuto-Scout:v1.0 (by /u/autonomous_media)"
    min_upvotes: int = 300
    min_upvote_ratio: float = 0.85
    min_words: int = 90
    max_words: int = 350
    max_new_items: int = 1

    def _get_oauth_token(self) -> str | None:
        """Fetch OAuth bearer token if client credentials are configured."""
        cid = self.client_id or settings.reddit_client_id
        secret = self.client_secret or settings.reddit_client_secret
        if not cid or not secret:
            return None

        try:
            auth = requests.auth.HTTPBasicAuth(cid, secret)
            headers = {"User-Agent": self.user_agent or settings.reddit_user_agent or "YTAuto-Scout:v1.0"}
            data = {"grant_type": "client_credentials"}
            res = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers, timeout=8.0)
            if res.status_code == 200:
                token = res.json().get("access_token")
                return token
        except Exception as e:
            logger.warning(f"Failed to obtain Reddit OAuth access token: {e}")
        return None

    def discover(self, existing_ids: set[str] | None = None) -> list[SourceItem]:
        """
        Polls top daily posts across target subreddits.
        Returns top qualifying SourceItem objects.
        """
        existing_ids = existing_ids or set()
        token = self._get_oauth_token()

        if token:
            base_url = "https://oauth.reddit.com"
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent or settings.reddit_user_agent or "YTAuto-Scout:v1.0",
            }
        else:
            base_url = "https://www.reddit.com"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }

        discovered: list[SourceItem] = []

        for subreddit in self.subreddits:
            if len(discovered) >= self.max_new_items:
                break

            endpoints = [
                f"{base_url}/r/{subreddit}/top.json?t=day&limit=25",
                f"{base_url}/r/{subreddit}/hot.json?limit=25",
            ]

            for endpoint in endpoints:
                if len(discovered) >= self.max_new_items:
                    break

                try:
                    res = requests.get(endpoint, headers=headers, timeout=8.0)
                    if res.status_code != 200:
                        continue

                    data = res.json()
                    posts = data.get("data", {}).get("children", [])

                    for p in posts:
                        post_data = p.get("data", {})
                        post_id = post_data.get("id")
                        if not post_id or post_id in existing_ids:
                            continue

                        # 1. Advertiser safety check
                        if post_data.get("over_18", False):
                            continue

                        raw_title = (post_data.get("title") or "").strip()
                        raw_body = (post_data.get("selftext") or "").strip()
                        if not raw_title or not raw_body:
                            continue

                        combined_lower = f"{raw_title} {raw_body}".lower()
                        if any(kw in combined_lower for kw in BLOCKED_KEYWORDS):
                            continue

                        # 2. Score & Ratio check
                        score = post_data.get("score", 0)
                        ratio = post_data.get("upvote_ratio", 0.0)
                        if score < self.min_upvotes or ratio < self.min_upvote_ratio:
                            continue

                        # 3. Clean body text & word count check
                        clean_body = clean_reddit_story_text(raw_body)
                        word_count = len(clean_body.split())
                        if not (self.min_words <= word_count <= self.max_words):
                            continue

                        permalink = f"https://www.reddit.com{post_data.get('permalink', '')}"
                        author = post_data.get("author", "Anonymous")
                        comments_count = post_data.get("num_comments", 0)

                        item = SourceItem(
                            external_id=post_id,
                            title=raw_title,
                            url=permalink,
                            published_at=str(post_data.get("created_utc", "")),
                        )
                        # Attach metadata for DB ingestion
                        setattr(item, "body_text", clean_body)
                        setattr(item, "subreddit", subreddit)
                        setattr(item, "author", author)
                        setattr(item, "score", score)
                        setattr(item, "comments_count", comments_count)

                        discovered.append(item)
                        existing_ids.add(post_id)

                        logger.info(
                            f"Discovered viral Reddit story: r/{subreddit} - '{raw_title[:60]}...' ({score} upvotes, {word_count} words)",
                            extra={"trace_id": f"scout-{post_id}"}
                        )

                        if len(discovered) >= self.max_new_items:
                            break

                except Exception as e:
                    logger.warning(f"Failed to poll Reddit endpoint {endpoint}: {e}")

        return discovered
