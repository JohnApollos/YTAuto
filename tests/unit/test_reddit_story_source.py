"""
tests/unit/test_reddit_story_source.py

Unit tests for the Automated Reddit Stories Acquisition Source.
"""

import pytest
from unittest.mock import patch, MagicMock
from autonomous_media.sources.reddit_story import (
    RedditStorySource, clean_reddit_story_text
)


def test_clean_reddit_story_text():
    raw = """
    This is my story [click here](https://reddit.com).
    http://example.com/some/link

    EDIT: Thank you all for the support!
    TL;DR: Sister got mad.
    """
    cleaned = clean_reddit_story_text(raw)
    assert "EDIT:" not in cleaned
    assert "TL;DR" not in cleaned
    assert "http" not in cleaned
    assert "This is my story click here." in cleaned


def test_reddit_story_source_discover():
    source = RedditStorySource(
        subreddits=["AmItheAsshole"],
        min_upvotes=100,
        min_upvote_ratio=0.80,
        min_words=10,
        max_words=200,
        max_new_items=1,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc1234",
                        "title": "AITA for not sharing my inheritance with my brother?",
                        "selftext": "My grandmother left me a small cabin in the woods because I took care of her for five years before she passed away. My brother never visited but now wants half.",
                        "score": 1500,
                        "upvote_ratio": 0.95,
                        "over_18": False,
                        "author": "cabin_heir",
                        "permalink": "/r/AmItheAsshole/comments/abc1234/",
                        "num_comments": 240,
                        "created_utc": 1787000000,
                    }
                }
            ]
        }
    }

    with patch("requests.get", return_value=mock_response):
        items = source.discover()

    assert len(items) == 1
    assert items[0].external_id == "abc1234"
    assert items[0].title == "AITA for not sharing my inheritance with my brother?"
    assert getattr(items[0], "subreddit") == "AmItheAsshole"
    assert getattr(items[0], "score") == 1500
    assert getattr(items[0], "author") == "cabin_heir"


def test_reddit_story_source_filters_nsfw_and_low_score():
    source = RedditStorySource(
        subreddits=["tifu"],
        min_upvotes=500,
        min_upvote_ratio=0.85,
        min_words=10,
        max_words=200,
        max_new_items=2,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "children": [
                {
                    # NSFW - should be skipped
                    "data": {
                        "id": "nsfw1",
                        "title": "NSFW Story",
                        "selftext": "Valid length story with lots of detail.",
                        "score": 2000,
                        "upvote_ratio": 0.95,
                        "over_18": True,
                    }
                },
                {
                    # Low score - should be skipped
                    "data": {
                        "id": "low_score",
                        "title": "Low Score Story",
                        "selftext": "Valid length story with lots of detail.",
                        "score": 50,
                        "upvote_ratio": 0.95,
                        "over_18": False,
                    }
                },
            ]
        }
    }

    with patch("requests.get", return_value=mock_response):
        items = source.discover()

    assert len(items) == 0
