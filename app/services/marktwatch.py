"""Marktwert-Ermittlung über marktwatch (node1).

Portiert aus saganta assets-api (Phase 3 Super-App-Merge 2026-07-03):
Median über bis zu 20 Kleinanzeigen-Preise, Ergebnis wird mit Zeitstempel
am Asset gecacht (TTL via MARKTWATCH_CACHE_TTL_MINUTES).
"""

from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.domain import DomainError
from app.models import ElectronicAsset


class MarketValueResult:
    def __init__(self, asset: ElectronicAsset, samples: int, from_cache: bool) -> None:
        self.asset = asset
        self.samples = samples
        self.from_cache = from_cache


def _cache_fresh(asset: ElectronicAsset) -> bool:
    if asset.market_value_at is None:
        return False
    at = asset.market_value_at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - at
    return age < timedelta(minutes=settings.MARKTWATCH_CACHE_TTL_MINUTES)


def refresh_market_value(asset: ElectronicAsset, force: bool = False) -> MarketValueResult:
    """Holt den Median-Marktpreis via marktwatch und schreibt ihn ans Asset.

    Commit macht der Aufrufer (Route). Wirft DomainError, wenn marktwatch
    nicht erreichbar ist: der gecachte Wert bleibt dann unangetastet.
    """
    if not force and _cache_fresh(asset):
        return MarketValueResult(asset, samples=0, from_cache=True)

    # ★ marktwatch ist eine optionale Anbindung an einen Dienst, den es nur in
    # dieser Installation gibt. Seit 2026-09-05 steht seine Adresse nicht mehr
    # als Vorbelegung im Quelltext (sie zeigte auf einen Rechner im Heimnetz).
    # Ohne Konfiguration hier abbrechen statt httpx eine Adresse ohne Wirt zu
    # geben: das waere ein InvalidURL, und der ist KEIN httpx.HTTPError, faele
    # also durch das except unten hindurch und kaeme als 500 heraus.
    if not settings.MARKTWATCH_BASE_URL:
        raise DomainError(
            "marktwatch ist nicht konfiguriert",
            {"hinweis": "MARKTWATCH_BASE_URL setzen, sonst bleibt der Marktwert leer"},
        )

    query = asset.name if not asset.category else f"{asset.name} {asset.category}"
    try:
        headers = (
            {"X-API-Key": settings.MARKTWATCH_API_KEY} if settings.MARKTWATCH_API_KEY else {}
        )
        r = httpx.post(
            f"{settings.MARKTWATCH_BASE_URL.rstrip('/')}/api/crawl/search",
            json={"query": query},
            headers=headers,
            timeout=settings.MARKTWATCH_TIMEOUT_SEC,
        )
    except httpx.HTTPError as e:
        raise DomainError("marktwatch nicht erreichbar", {"error": str(e)}) from e
    if r.status_code >= 400:
        raise DomainError("marktwatch-Fehler", {"status": r.status_code, "body": r.text[:200]})

    results = r.json() if r.content else []
    prices = sorted(
        float(x["price"]) for x in results if isinstance(x, dict) and x.get("price")
    )
    # Echter Median: bei gerader Anzahl der Mittelwert der beiden mittleren Preise
    # (vorher wurde der obere Mittelwert genommen → verzerrt den Marktwert nach oben).
    n = len(prices)
    if n == 0:
        median = None
    elif n % 2:
        median = prices[n // 2]
    else:
        median = (prices[n // 2 - 1] + prices[n // 2]) / 2

    asset.market_value_eur = median
    asset.market_value_at = datetime.now(timezone.utc)
    return MarketValueResult(asset, samples=len(prices), from_cache=False)
