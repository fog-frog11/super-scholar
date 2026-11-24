from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db import SessionLocal
from app.migrations import upgrade_database
from app.services.venue_catalog import CatalogUnavailable, VenueCatalogService


async def refresh() -> None:
    upgrade_database()
    settings = get_settings()
    with SessionLocal() as session:
        service = VenueCatalogService(session, settings)
        failures: list[str] = []
        for kind in ("journal", "conference"):
            try:
                result = await service.get(kind, force_refresh=True)
            except CatalogUnavailable as exc:
                failures.append(f"{kind}: {exc}")
                print(f"{kind}: unavailable | {exc}")
                continue
            print(
                f"{kind}: {len(result.items)} records | "
                f"{result.source_label} | {result.fetched_at.isoformat()} | stale={result.stale}"
            )
        if failures:
            raise SystemExit("venue refresh incomplete: " + " | ".join(failures))


def main() -> None:
    asyncio.run(refresh())


if __name__ == "__main__":
    main()
