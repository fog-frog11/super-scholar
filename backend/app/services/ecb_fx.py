from __future__ import annotations

from dataclasses import dataclass
import csv
from io import StringIO
from typing import Any

import httpx

ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD+CNY.EUR.SP00.A"


@dataclass(frozen=True)
class FxRate:
    cny_per_usd: float
    date: str
    source_url: str
    provider: str = "ECB"

    def as_dict(self) -> dict[str, Any]:
        return {"cnyPerUsd": self.cny_per_usd, "date": self.date, "sourceUrl": self.source_url, "provider": self.provider}


async def latest_cny_per_usd(client: httpx.AsyncClient) -> FxRate | None:
    """Fetch the latest ECB reference rates and derive CNY per USD.

    ECB EXR quotes USD and CNY as units per EUR. Therefore CNY/USD is
    (CNY per EUR) / (USD per EUR). If either observation is missing we return
    None rather than reusing a stale or guessed FX value.
    """
    response = await client.get(
        ECB_URL,
        params={"lastNObservations": 1, "format": "csvdata"},
        headers={"Accept": "text/csv", "User-Agent": "SuperScholar/3.11.0 APC-FX"},
        follow_redirects=True,
    )
    response.raise_for_status()
    rows = list(csv.DictReader(StringIO(response.text)))
    rates: dict[str, tuple[float, str]] = {}
    for row in rows:
        currency = str(row.get("CURRENCY") or row.get("KEY") or "").strip().upper()
        value_raw = row.get("OBS_VALUE")
        if currency not in {"USD", "CNY"} or value_raw in {None, ""}:
            continue
        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            continue
        date = str(row.get("TIME_PERIOD") or row.get("TIME_PERIOD_START") or "").strip()
        rates[currency] = (value, date)
    if "USD" not in rates or "CNY" not in rates or rates["USD"][0] <= 0:
        return None
    cny_per_usd = rates["CNY"][0] / rates["USD"][0]
    date = max(rates["USD"][1], rates["CNY"][1])
    return FxRate(cny_per_usd=round(cny_per_usd, 8), date=date, source_url=str(response.url))
