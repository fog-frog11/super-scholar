from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import VenueCache
from app.services import venue_catalog as catalog_module
from app.services.venue_catalog import VenueCatalogService


def test_stale_last_success_cache_is_used_when_refresh_fails(monkeypatch):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.get(VenueCache, "journal") or VenueCache(kind="journal")
        existing.payload_json = [{"id": "journal:test", "type": "journal", "name": "Test", "ccf": "A"}]
        existing.source_url = "https://example.invalid/source"
        existing.source_label = "last successful source"
        existing.source_tier = "official"
        existing.checksum = "abc"
        existing.fetched_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        existing.last_error = None
        db.add(existing)
        db.commit()

        async def fail(_client):
            raise RuntimeError("upstream unavailable")

        monkeypatch.setattr(catalog_module, "fetch_journals", fail)
        result = asyncio.run(VenueCatalogService(db, get_settings()).get("journal", force_refresh=True))
        assert result.stale is True
        assert result.source_tier == "cache"
        assert result.items[0]["id"] == "journal:test"
        assert "upstream unavailable" in (result.last_error or "")


def test_pre_v37_catalog_schema_forces_refresh():
    """A just-fetched V3.6 payload must not stay 'fresh' after upgrading to V3.7."""
    with SessionLocal() as db:
        service = VenueCatalogService(db, get_settings())
        old_journal = VenueCache(
            kind="journal",
            payload_json=[{"id": "journal:ai:a:legacy", "type": "journal", "name": "Legacy", "ccf": "A"}],
            source_url="https://example.test",
            source_label="legacy",
            source_tier="official",
            checksum="legacy",
            fetched_at=datetime.now(timezone.utc),
        )
        new_journal = VenueCache(
            kind="journal",
            payload_json=[{"id": "journal:legacy", "seriesId": "journal:legacy", "type": "journal", "name": "Legacy", "ccf": "A", "ccfVerified": True, "ccfEntries": [{"sub":"AI","ccf":"A"}]}],
            source_url="https://example.test",
            source_label="v3.7",
            source_tier="official",
            checksum="v37",
            fetched_at=datetime.now(timezone.utc),
        )
        assert service._is_fresh(old_journal) is False
        assert service._is_fresh(new_journal) is True
