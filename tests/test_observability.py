"""Tests für /api/health, /metrics, Request-ID-Propagation und DomainError-Payload."""

from app.main import APP_VERSION


def test_api_health_returns_status_db_version(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["version"] == APP_VERSION


def test_legacy_health_still_works(client):
    """Externe Health-Checker dürfen weiter /health nutzen."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_metrics_endpoint_exposes_prometheus_format(client):
    # Mindestens ein scrape muss vorher passiert sein, damit Counter Werte haben.
    client.get("/api/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Prometheus text format hat HELP/TYPE-Header-Zeilen
    assert "# HELP" in body
    assert "# TYPE" in body
    # Der Instrumentator emittiert http_requests_total
    assert "http_request" in body


def test_request_id_generated_when_missing(client):
    resp = client.get("/api/health")
    rid = resp.headers.get("x-request-id")
    assert rid is not None
    assert len(rid) >= 16


def test_request_id_propagated_when_provided(client):
    custom_rid = "test-rid-abc-12345"
    resp = client.get("/api/health", headers={"x-request-id": custom_rid})
    assert resp.headers.get("x-request-id") == custom_rid


def test_domain_error_payload_includes_request_id(client):
    custom_rid = "domain-err-rid-42"
    resp = client.get("/api/products/9999", headers={"x-request-id": custom_rid})
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["request_id"] == custom_rid
