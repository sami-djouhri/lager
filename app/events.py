"""HTTP-Producer für den Homelab Event Spine.

Sendet best-effort POSTs an life-ops-api `/api/events`. Lager darf NICHT
crashen, wenn life-ops-api down ist: Fehler werden geloggt und geschluckt.

Hash-Idempotenz wird Server-seitig durch denselben sha256-Algo abgesichert
(siehe life-ops-api `app/api/routes_events.py`). Wir senden plain JSON,
der Sink berechnet den Hash und antwortet 201 (neu) bzw. 409 (Duplikat).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.logging import get_logger

logger = get_logger("lager.events")

# Kanonische event_type-Strings aus life-ops-api app/event_types.py.
# Diese müssen exakt matchen, sonst antwortet der Sink 422.
INVENTORY_RESTOCKED = "inventory.restocked"
INVENTORY_UPDATED = "inventory.updated"
INVENTORY_LOW_STOCK = "inventory.low_stock"


def emit(
    *,
    event_type: str,
    external_id: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    severity: str = "info",
    entity_ref: str | None = None,
    occurred_at: datetime | None = None,
) -> bool:
    """Sendet ein Event an life-ops-api. Returnt True bei 201, False sonst.

    Nicht-blockierend im Sinne von: Fehler werden geloggt, nicht geraised.
    """
    if not settings.EVENT_EMISSION_ENABLED:
        return False

    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)
    elif occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    body = {
        "event_type": event_type,
        "source": settings.EVENT_SOURCE,
        "external_id": external_id,
        "occurred_at": occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary[:400],
        "severity": severity,
        "entity_ref": entity_ref,
        "payload": payload or {},
    }

    url = f"{settings.LIFE_OPS_URL.rstrip('/')}/api/events"
    try:
        with httpx.Client(timeout=settings.EVENT_EMIT_TIMEOUT_SEC) as client:
            resp = client.post(url, json=body)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        logger.warning(
            "event_emit_network_error",
            event_type=event_type,
            external_id=external_id,
            error=str(exc),
        )
        return False
    except Exception as exc:
        logger.warning(
            "event_emit_unexpected_error",
            event_type=event_type,
            external_id=external_id,
            error=str(exc),
        )
        return False

    if resp.status_code == 201:
        logger.info(
            "event_emitted",
            event_type=event_type,
            external_id=external_id,
        )
        return True
    if resp.status_code == 409:
        # Duplikat: passiert legitim bei Idempotenz-Replays.
        logger.debug(
            "event_duplicate",
            event_type=event_type,
            external_id=external_id,
        )
        return False
    logger.warning(
        "event_emit_rejected",
        event_type=event_type,
        external_id=external_id,
        status=resp.status_code,
        body=resp.text[:300],
    )
    return False
