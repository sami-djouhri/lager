"""marktwatch ohne Konfiguration bricht sauber ab.

Die Adresse von marktwatch stand bis zum 2026-09-05 als Vorbelegung im
Quelltext und zeigte auf einen Rechner im Heimnetz. Seither ist sie leer, weil
dieses Repo veroeffentlicht werden soll und ein Selbsthoster diesen Dienst nicht
hat.

★ Der Test sichert genau den Fall ab, der dabei leicht uebersehen wird: mit
leerer Adresse ginge der Aufruf an einen Pfad ohne Wirt. httpx wirft dafuer
``InvalidURL``, und das ist **kein** ``httpx.HTTPError``. Der bestehende
except-Zweig haette ihn also nicht gefangen, und aus einer fehlenden
Konfiguration waere ein 500 geworden statt einer Meldung, die sagt, was fehlt.
"""

import pytest

from app.config import settings
from app.domain import DomainError
from app.services import marktwatch


class _Asset:
    """Minimal, damit der Cache-Zweig nicht greift und wir am Aufruf landen."""

    id = 1
    name = "Testgeraet"
    category = None
    market_value_cents = None
    market_value_at = None


def test_ohne_adresse_klare_meldung_statt_500(monkeypatch):
    monkeypatch.setattr(settings, "MARKTWATCH_BASE_URL", "")
    with pytest.raises(DomainError) as f:
        marktwatch.refresh_market_value(_Asset(), force=True)
    assert "nicht konfiguriert" in str(f.value)


def test_mit_adresse_wird_der_aufruf_versucht(monkeypatch):
    """Gegenprobe: die Sperre darf nicht immer greifen, sonst ist sie ein Aus-Schalter."""
    monkeypatch.setattr(settings, "MARKTWATCH_BASE_URL", "http://192.0.2.10:8120")

    def _fehlschlag(*a, **k):
        raise marktwatch.httpx.ConnectError("kein Netz im Test")

    monkeypatch.setattr(marktwatch.httpx, "post", _fehlschlag)
    with pytest.raises(DomainError) as f:
        marktwatch.refresh_market_value(_Asset(), force=True)
    # Andere Meldung als oben: der Aufruf wurde versucht und scheiterte am Netz.
    assert "nicht erreichbar" in str(f.value)
