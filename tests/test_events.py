"""Tests für Event-Spine-Producer (POST /api/events an life-ops-api).

Wir patchen httpx.Client.post, damit kein echter Netzaufruf passiert, und
verifizieren das Payload-Format gegen das life-ops-api `EventIn`-Schema.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app import events
from app.config import settings


@pytest.fixture
def emission_enabled():
    """Aktiviert EVENT_EMISSION_ENABLED nur für diesen Test (conftest setzt False)."""
    original = settings.EVENT_EMISSION_ENABLED
    settings.EVENT_EMISSION_ENABLED = True
    try:
        yield
    finally:
        settings.EVENT_EMISSION_ENABLED = original


@pytest.fixture
def mock_post():
    """Patcht httpx.Client.post mit 201-Response. Returnt das Mock-Objekt."""
    with patch("app.events.httpx.Client") as cli_cls:
        post_mock = MagicMock()
        post_mock.return_value = MagicMock(status_code=201, text="ok")
        cli_cls.return_value.__enter__.return_value.post = post_mock
        yield post_mock


def test_emit_disabled_returns_false_without_call(mock_post):
    # conftest setzt EVENT_EMISSION_ENABLED=false; ohne emission_enabled bleibt's so.
    ok = events.emit(
        event_type=events.INVENTORY_UPDATED,
        external_id="product:1:2026-06-12",
        summary="Test",
    )
    assert ok is False
    mock_post.assert_not_called()


def test_emit_sends_valid_payload(emission_enabled, mock_post):
    ok = events.emit(
        event_type=events.INVENTORY_RESTOCKED,
        external_id="stock-entry:42",
        summary="500g Mehl eingebucht",
        entity_ref="product:7",
        payload={"product_id": 7, "quantity": 500, "unit": "g"},
    )
    assert ok is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["event_type"] == "inventory.restocked"
    assert body["source"] == settings.EVENT_SOURCE
    assert body["external_id"] == "stock-entry:42"
    assert body["entity_ref"] == "product:7"
    assert body["payload"] == {"product_id": 7, "quantity": 500, "unit": "g"}
    assert body["severity"] == "info"
    # ISO-8601 UTC, sekunden-genau
    assert body["occurred_at"].endswith("Z")


def test_emit_handles_conflict_as_duplicate(emission_enabled):
    """409 vom Sink = Idempotenz-Replay → kein Crash, return False."""
    with patch("app.events.httpx.Client") as cli_cls:
        cli_cls.return_value.__enter__.return_value.post = MagicMock(
            return_value=MagicMock(status_code=409, text="duplicate")
        )
        ok = events.emit(
            event_type=events.INVENTORY_UPDATED,
            external_id="product:1:2026-06-12",
            summary="dup",
        )
        assert ok is False


def test_emit_swallows_network_errors(emission_enabled):
    """Spine offline → Lager-Aufrufer darf NICHT crashen."""
    import httpx
    with patch("app.events.httpx.Client") as cli_cls:
        cli_cls.return_value.__enter__.return_value.post = MagicMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        # darf nicht raisen
        ok = events.emit(
            event_type=events.INVENTORY_UPDATED,
            external_id="product:1:2026-06-12",
            summary="net-down",
        )
        assert ok is False


def test_add_stock_emits_restocked_event(client, emission_enabled, mock_post):
    pid = client.post("/api/products", json={"name": "Mehl", "default_unit": "g"}).json()["id"]

    resp = client.post("/api/stock", json={"product_id": pid, "quantity": 500, "unit": "g"})
    assert resp.status_code == 201

    # mindestens ein Restock-Event muss raus gegangen sein
    calls = mock_post.call_args_list
    event_types = [c.kwargs["json"]["event_type"] for c in calls]
    assert "inventory.restocked" in event_types


def test_consume_below_min_stock_emits_low_stock_event(client, emission_enabled, mock_post):
    # Produkt mit min_stock=100, dann auf 30 leerverbrauchen.
    pid = client.post("/api/products", json={
        "name": "Reis", "default_unit": "g", "min_stock": 100, "min_stock_unit": "g",
    }).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 130, "unit": "g"})

    mock_post.reset_mock()
    resp = client.post("/api/stock/consume", json={"product_id": pid, "amount": 100, "unit": "g"})
    assert resp.status_code == 200

    event_types = [c.kwargs["json"]["event_type"] for c in mock_post.call_args_list]
    assert "inventory.updated" in event_types
    assert "inventory.low_stock" in event_types

    # severity-Mapping prüfen: 30g > 0 → medium
    low_calls = [
        c for c in mock_post.call_args_list
        if c.kwargs["json"]["event_type"] == "inventory.low_stock"
    ]
    assert low_calls[0].kwargs["json"]["severity"] == "medium"


def test_consume_to_zero_emits_high_severity(client, emission_enabled, mock_post):
    pid = client.post("/api/products", json={
        "name": "Salz", "default_unit": "g", "min_stock": 50, "min_stock_unit": "g",
    }).json()["id"]
    client.post("/api/stock", json={"product_id": pid, "quantity": 30, "unit": "g"})

    mock_post.reset_mock()
    client.post("/api/stock/consume", json={"product_id": pid, "amount": 30, "unit": "g"})

    low_calls = [
        c for c in mock_post.call_args_list
        if c.kwargs["json"]["event_type"] == "inventory.low_stock"
    ]
    assert low_calls, "low_stock-Event fehlt"
    assert low_calls[0].kwargs["json"]["severity"] == "high"
