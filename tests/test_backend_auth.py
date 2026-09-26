"""Regression tests fuer die fail-closed Bearer-Verifikation (app/backend_auth.py).

Sichert den Sicherheitsfix von 2026-07-06 ab: native Apps schicken ein HS256-JWT
(aud=lager-api) vom saganta-auth-service; jeder ungueltige Bearer MUSS 401 geben
(kein Fallback auf DEFAULT_OWNER_SUB). Stdlib-HS256, keine externe JWT-Lib.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException

from app import backend_auth
from app.config import settings

SECRET = "test-secret-abc123"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _mint(sub="USER-1", aud="lager-api", iss="saganta", exp_delta=120, secret=SECRET):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64(
        json.dumps(
            {"iss": iss, "sub": sub, "email": "x@y.z", "aud": aud,
             "iat": now, "exp": now + exp_delta}
        ).encode()
    )
    sig = _b64(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch):
    monkeypatch.setattr(settings, "SAGANTA_BACKEND_SECRET", SECRET)


def test_valid_token_returns_sub():
    assert backend_auth.sub_from_bearer("Bearer " + _mint(sub="USER-ABC")) == "USER-ABC"


def test_bad_signature_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint() + "tampered")
    assert exc.value.status_code == 401


def test_wrong_audience_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint(aud="news-api"))
    assert exc.value.status_code == 401


def test_wrong_issuer_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint(iss="evil"))
    assert exc.value.status_code == 401


def test_expired_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint(exp_delta=-300))
    assert exc.value.status_code == 401


def test_foreign_secret_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint(secret="attacker-secret"))
    assert exc.value.status_code == 401


def test_malformed_token_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer notajwt")
    assert exc.value.status_code == 401


def test_no_sub_rejected():
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint(sub=""))
    assert exc.value.status_code == 401


def test_backend_secret_unconfigured_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SAGANTA_BACKEND_SECRET", "")
    with pytest.raises(HTTPException) as exc:
        backend_auth.sub_from_bearer("Bearer " + _mint())
    assert exc.value.status_code == 401
