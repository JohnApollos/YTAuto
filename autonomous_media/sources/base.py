from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class SourceItem:
    """A single discovered item from a ContentSource — the raw reference before download."""
    external_id: str     # e.g. YouTube video ID
    title: str
    url: str
    published_at: str | None = None  # ISO 8601 string


@dataclass
class RawMedia:
    """The result of fetch() — paths/keys to the downloaded media."""
    source_item: SourceItem
    video_path: str | None = None   # local temp path or MinIO key
    audio_path: str | None = None
    metadata: dict | None = None


@runtime_checkable
class ContentSource(Protocol):
    """Spec §11.3: the plugin interface every content source implements.
    Adding a new source type means implementing this Protocol — not changing
    the Scheduler, the editing engine, or anything downstream.
    """

    def discover(self) -> list[SourceItem]:
        """Return items that are new since the last poll."""
        ...

    def fetch(self, item: SourceItem) -> RawMedia:
        """Download/retrieve the raw media for a discovered item."""
        ...
