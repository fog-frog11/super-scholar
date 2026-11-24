from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import VenueCache
from ..services.venue_catalog import CatalogResult, CatalogUnavailable, VenueCatalogService

router = APIRouter(prefix="/venues", tags=["venues"])


def _response(result: CatalogResult) -> dict:
    return {
        "count": len(result.items),
        "items": result.items,
        "meta": {
            "kind": result.kind,
            "source": result.source_url,
            "sourceLabel": result.source_label,
            "sourceTier": result.source_tier,
            "fetchedAt": result.fetched_at,
            "stale": result.stale,
            "checksum": result.checksum,
            "lastRefreshError": result.last_error,
        },
    }


async def _get(kind: str, refresh: bool, db: Session, settings: Settings) -> dict:
    service = VenueCatalogService(db, settings)
    try:
        return _response(await service.get(kind, force_refresh=refresh))  # type: ignore[arg-type]
    except CatalogUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "venue_source_unavailable", "message": str(exc)}) from exc


@router.get("/journals")
async def journals(
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await _get("journal", refresh, db, settings)


@router.get("/conferences")
async def conferences(
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await _get("conference", refresh, db, settings)


@router.get("/status")
def venue_status(db: Session = Depends(get_db)) -> dict:
    result: dict[str, dict | None] = {}
    for kind in ("journal", "conference"):
        cache = db.get(VenueCache, kind)
        result[kind] = None if cache is None else {
            "source": cache.source_url,
            "sourceLabel": cache.source_label,
            "sourceTier": cache.source_tier,
            "fetchedAt": cache.fetched_at,
            "checksum": cache.checksum,
            "count": len(cache.payload_json),
            "lastError": cache.last_error,
        }
    return result
