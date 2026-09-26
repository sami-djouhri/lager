"""Der Anfragedeckel unterscheidet einen Nachbardienst von einem Browser.

★★ Der Anlass, gemessen am 2026-09-13: der Deckel von 60 je Minute ist gegen
einen durchdrehenden Browser gedacht, traf aber mealprep. Eine Einkaufsliste
aus 47 Zutaten braucht in Sekunden mehr Anfragen, als ein Mensch in einer
Minute klickt. Der Rest kam als 429, und der Adapter drueben macht aus jedem
Fehler eine Null: die Liste entstand aus lauter Nullen und sah plausibel aus.

Unterschieden wird an der Signatur, nicht an der Adresse: ``X-Saganta-Sub-Sig``
kann nur erzeugen, wer das Geheimnis dieses Dienstes kennt. Getestet wird die
Entscheidungsfunktion direkt, nicht ueber echte Anfragen im Sekundentakt: die
Suite laeuft ohnehin mit abgeschaltetem Deckel (``conftest``), und ein Test,
der 600 Anfragen abfeuert, misst am Ende die Geschwindigkeit des Testrechners.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.main import RATE_LIMIT, RATE_LIMIT_DIENST, _absender_und_grenze
from app.tenant_auth import erwartete_signatur

SUB = "auth0|beispielnutzer"
GEHEIMNIS = "geheim-fuer-den-test"


class _Anfrage:
    """Das Wenige, das ``_absender_und_grenze`` von einem Request liest."""

    class _Gegenstelle:
        def __init__(self, host: str):
            self.host = host

    def __init__(self, headers: dict[str, str] | None = None, ip: str = "10.0.0.9"):
        self.headers = headers or {}
        self.client = self._Gegenstelle(ip)


@pytest.fixture
def mit_geheimnis(monkeypatch):
    monkeypatch.setattr(settings, "LAGER_TENANT_SECRET", GEHEIMNIS)


@pytest.fixture
def ohne_geheimnis(monkeypatch):
    monkeypatch.setattr(settings, "LAGER_TENANT_SECRET", "")


def test_browser_behaelt_den_engen_deckel(mit_geheimnis):
    absender, grenze = _absender_und_grenze(_Anfrage())
    assert absender == "10.0.0.9"
    assert grenze == RATE_LIMIT


def test_signierter_dienst_bekommt_das_weitere_kontingent(mit_geheimnis):
    kopf = {
        "x-saganta-sub": SUB,
        "x-saganta-sub-sig": erwartete_signatur(SUB, GEHEIMNIS),
    }
    absender, grenze = _absender_und_grenze(_Anfrage(kopf))
    assert absender == f"dienst:{SUB}"
    assert grenze == RATE_LIMIT_DIENST
    assert RATE_LIMIT_DIENST > RATE_LIMIT


def test_eigener_zaehler_statt_des_ip_zaehlers(mit_geheimnis):
    """Der Mensch am selben Rechner darf sein Kontingent nicht verlieren.

    Beide kommen ueber dieselbe Adresse herein. Teilten sie sich einen Zaehler,
    haette der Dienst dem Browser das Kontingent weggenommen, und der Nutzer
    saehe 429 in einer App, die er gerade erst geoeffnet hat.
    """
    kopf = {
        "x-saganta-sub": SUB,
        "x-saganta-sub-sig": erwartete_signatur(SUB, GEHEIMNIS),
    }
    dienst, _ = _absender_und_grenze(_Anfrage(kopf, ip="127.0.0.1"))
    browser, _ = _absender_und_grenze(_Anfrage(ip="127.0.0.1"))
    assert dienst != browser


def test_falsche_signatur_zaehlt_als_browser(mit_geheimnis):
    kopf = {"x-saganta-sub": SUB, "x-saganta-sub-sig": "0" * 64}
    absender, grenze = _absender_und_grenze(_Anfrage(kopf))
    assert absender == "10.0.0.9"
    assert grenze == RATE_LIMIT


def test_sub_ohne_signatur_zaehlt_als_browser(mit_geheimnis):
    absender, grenze = _absender_und_grenze(_Anfrage({"x-saganta-sub": SUB}))
    assert absender == "10.0.0.9"
    assert grenze == RATE_LIMIT


def test_ohne_geheimnis_bleibt_es_fuer_alle_beim_alten(ohne_geheimnis):
    """Kein stiller Verlust an Schutz im Auslieferungszustand.

    Ist kein Geheimnis vergeben, laesst sich ein Dienst nicht von einem
    Browser unterscheiden. Dann darf auch niemand mehr duerfen: sonst reichte
    ein geratener Header, um den Deckel zu verzehnfachen.
    """
    kopf = {
        "x-saganta-sub": SUB,
        "x-saganta-sub-sig": erwartete_signatur(SUB, GEHEIMNIS),
    }
    absender, grenze = _absender_und_grenze(_Anfrage(kopf))
    assert absender == "10.0.0.9"
    assert grenze == RATE_LIMIT


def test_ohne_gegenstelle_kein_absturz(mit_geheimnis):
    anfrage = _Anfrage()
    anfrage.client = None
    absender, grenze = _absender_und_grenze(anfrage)
    assert absender == "unknown"
    assert grenze == RATE_LIMIT
