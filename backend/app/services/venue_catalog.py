from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import VenueCache
from .ccf import fetch_journals
from .ccfddl import fetch_conferences

Kind = Literal["journal", "conference"]


class CatalogUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogResult:
    kind: Kind
    items: list[dict[str, Any]]
    source_url: str
    source_label: str
    source_tier: str
    fetched_at: datetime
    checksum: str
    stale: bool
    last_error: str | None = None


def _checksum(items: list[dict[str, Any]]) -> str:
    data = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class VenueCatalogService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def _cache(self, kind: Kind) -> VenueCache | None:
        return self.db.get(VenueCache, kind)

    def _schema_is_current(self, cache: VenueCache) -> bool:
        """Invalidate pre-V3.7 catalog rows after an in-place upgrade.

        The venue cache is intentionally persistent, so a time-fresh V3.6 payload can
        survive a code upgrade. V3.7 needs stable series IDs and full conference
        timelines/CCF provenance; missing fields therefore force one refresh instead of
        silently running the new recommender against the old schema.
        """
        items = cache.payload_json if isinstance(cache.payload_json, list) else []
        sample = next((item for item in items if isinstance(item, dict)), None)
        if sample is None:
            return False
        if cache.kind == "journal":
            return bool(sample.get("seriesId")) and sample.get("ccfVerified") is True and isinstance(sample.get("ccfEntries"), list)
        if cache.kind == "conference":
            return bool(sample.get("seriesId")) and isinstance(sample.get("timeline"), list) and bool(sample.get("ccfSource"))
        return False

    def _is_fresh(self, cache: VenueCache) -> bool:
        if not self._schema_is_current(cache):
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.settings.venue_cache_ttl_hours)
        fetched = cache.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return fetched >= cutoff

    def _from_cache(self, cache: VenueCache, stale: bool, error: str | None = None) -> CatalogResult:
        return CatalogResult(
            kind=cache.kind,  # type: ignore[arg-type]
            items=cache.payload_json,
            source_url=cache.source_url,
            source_label=cache.source_label,
            source_tier="cache" if stale else cache.source_tier,
            fetched_at=cache.fetched_at,
            checksum=cache.checksum,
            stale=stale,
            last_error=error or cache.last_error,
        )

    def _save(self, kind: Kind, items: list[dict[str, Any]], source_url: str, source_label: str, source_tier: str) -> VenueCache:
        cache = self._cache(kind) or VenueCache(kind=kind)
        cache.payload_json = items
        cache.source_url = source_url
        cache.source_label = source_label
        cache.source_tier = source_tier
        cache.checksum = _checksum(items)
        cache.fetched_at = datetime.now(timezone.utc)
        cache.last_error = None
        self.db.add(cache)
        self.db.commit()
        self.db.refresh(cache)
        return cache

    async def get(self, kind: Kind, force_refresh: bool = False) -> CatalogResult:
        cache = self._cache(kind)
        if cache and self._is_fresh(cache) and not force_refresh:
            return self._from_cache(cache, stale=False)

        timeout = httpx.Timeout(self.settings.outbound_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if kind == "journal":
                    fetched = await fetch_journals(client)
                else:
                    fetched = await fetch_conferences(client)
            saved = self._save(kind, fetched.items, fetched.source_url, fetched.source_label, fetched.source_tier)
            return self._from_cache(saved, stale=False)
        except Exception as exc:
            message = str(exc)
            if cache:
                cache.last_error = message
                self.db.add(cache)
                self.db.commit()
                return self._from_cache(cache, stale=True, error=message)
            raise CatalogUnavailable(message) from exc
