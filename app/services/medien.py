"""Die Anbindung an den medien-Katalog (Stufe 5, Bereich Filme & Medien).

Nur das Lager ruft medien, nie umgekehrt (Entscheid 2026-11-01): es sucht
Titel, legt fehlende an und meldet den physischen Bestand als Spiegel. So
reicht EIN Schluessel (`MEDIEN_TOKEN` hier, `secrets/lager_token` dort), und
medien braucht keinen Weg ins Lager. Der Weg laeuft ueber `cc-apps`
(`http://medien:8000`), medien laesst ihn als Maschinenweg mit Token zu.

Der Spiegel ist ein **ganzer Abzug**, keine Einzelmeldung: bei hoechstens
ein paar tausend Stueck ist das ein Aufruf, und ein verlorener Aufruf richtet
sich beim naechsten von selbst. Gesendet wird nach jeder Aenderung (entprellt)
und alle `SPIEGEL_TAKT` Sekunden. medien behaelt den letzten Stand mit
Zeitstempel: ist das Lager aus, steht dort „Stand von …", statt dass sich die
Fehlt-Liste mit 700 Titeln fuellt.

Ist medien aus, geht das Einbuchen trotzdem (seit 2026-11-01, „Verbindung
verbessern"): das Stueck entsteht ohne `titel_id` mit dem Namen von der
Huelle, und der Spiegel-Laeufer traegt den Titel vor dem naechsten Abzug nach
(`titel_nachtragen`). Vorher brach der ganze Einbuch-Lauf ab, sobald medien
neu startete. Nach einem Fehlschlag wartet der Laeufer nicht den vollen Takt,
sondern 1, 2, 4 … Minuten (`_pause`), und `zustand()` sagt der Startseite und
/metrics, seit wann die Verbindung fehlt.

medien ist einbenutzig („bleibt meine"): der Bereich ist nur im Mandanten
offen, dem der Katalog gehoert (`DEFAULT_OWNER_SUB`), und der Spiegel enthaelt
nur dessen Stuecke.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import DomainError
from app.logging import get_logger

logger = get_logger(__name__)

BEREICH = "medien"
SPIEGEL_TAKT = 900
KOPF = "X-Lager-Token"


def konfiguriert() -> bool:
    return bool(settings.MEDIEN_BASE_URL and settings.MEDIEN_TOKEN)


def _mandant(db: Session) -> str:
    return db.info.get("owner_sub") or settings.DEFAULT_OWNER_SUB


def offen(db: Session) -> bool:
    return konfiguriert() and _mandant(db) == settings.DEFAULT_OWNER_SUB


def warum_zu(db: Session) -> str:
    if not konfiguriert():
        return "Wartet auf die Anbindung an medien (der Schlüssel fehlt noch)."
    return "Nur im Konto, dem der medien-Katalog gehört."


def pruefe_offen(db: Session) -> None:
    if not offen(db):
        raise DomainError(warum_zu(db), {"bereich": BEREICH})


class NichtErreichbar(DomainError):
    pass


class Verbindung:
    """Was der Laeufer zuletzt erlebt hat (Prozess-Speicher, nach Neustart leer)."""

    def __init__(self) -> None:
        self.erfolg: datetime | None = None
        self.fehler_seit: datetime | None = None
        self.grund: str | None = None
        self.versuche = 0

    def ok(self) -> None:
        self.erfolg = datetime.now(timezone.utc)
        self.fehler_seit, self.grund, self.versuche = None, None, 0

    def gescheitert(self, grund: str) -> None:
        if self.fehler_seit is None:
            self.fehler_seit = datetime.now(timezone.utc)
        self.grund, self.versuche = grund, self.versuche + 1


verbindung = Verbindung()


def _pause() -> float:
    """Takt nach Erfolg, nach Fehlschlaegen 60 s, 120 s, 240 s … bis zum Takt."""
    if not verbindung.versuche:
        return SPIEGEL_TAKT
    return min(SPIEGEL_TAKT, 60 * 2 ** (verbindung.versuche - 1))


def _ruf(methode: str, pfad: str, **kw) -> dict | list:
    kw.setdefault("timeout", settings.MEDIEN_TIMEOUT_SEC)
    try:
        antwort = httpx.request(
            methode, f"{settings.MEDIEN_BASE_URL.rstrip('/')}{pfad}",
            headers={KOPF: settings.MEDIEN_TOKEN}, **kw,
        )
    except httpx.HTTPError as fehler:
        logger.warning("medien_nicht_erreichbar", pfad=pfad, fehler=type(fehler).__name__)
        raise NichtErreichbar(
            "medien ist gerade nicht erreichbar. Filme & Medien lassen sich erst wieder "
            "einbuchen, wenn es läuft; der übrige Lauf geht weiter.", {}) from fehler
    if antwort.status_code == 403:
        # Ein falscher Schluessel liest sich sonst wie ein toter Dienst.
        raise DomainError("medien lehnt den Schlüssel des Lagers ab (403).", {})
    if antwort.status_code >= 400:
        raise DomainError(f"medien antwortet {antwort.status_code}",
                          {"pfad": pfad, "status": antwort.status_code})
    return antwort.json()


def titel_suchen(q: str) -> list[dict]:
    if not (q or "").strip():
        return []
    return list(_ruf("GET", "/api/lager/titel", params={"q": q.strip()}))


class IsbnUnbekannt(DomainError):
    """medien kennt die ISBN nicht, auch DNB und Open Library nicht."""


# DNB und Open Library nacheinander, je 8 s in medien (`isbn._holen`).
ISBN_TIMEOUT_SEC = 20.0


def titel_holen(name: str, medientyp: str | None, isbn: str | None = None) -> dict:
    """Den Titel zum Namen, und wenn es ihn nicht gibt, angelegt.

    Die Zuordnung macht medien (`titel_finden`: zwei Jahre sind zwei Werke),
    nicht das Lager. Eine zweite Namenslogik hier liefe auseinander.

    Mit `isbn` und ohne Namen schlaegt medien das Buch selbst nach (Katalog,
    sonst DNB und Open Library, je Buch einzeln auf den Scan hin, medien RICHTUNG
    Stufe 6). Kennt es die Nummer nicht, kommt `IsbnUnbekannt`.
    """
    body = {"titel": name, "medientyp": medientyp}
    if not isbn:
        return dict(_ruf("POST", "/api/lager/titel", json=body))
    try:
        return dict(_ruf("POST", "/api/lager/titel", json={**body, "isbn": isbn},
                         timeout=ISBN_TIMEOUT_SEC))
    except NichtErreichbar:
        raise
    except DomainError as fehler:
        if not name and fehler.details.get("status") == 422:
            raise IsbnUnbekannt(f"Die ISBN {isbn} kennen weder medien noch DNB und Open Library.",
                                {}) from fehler
        raise


def titel_nachtragen(db: Session) -> int:
    """Stuecke ohne Katalogtitel (eingebucht, waehrend medien aus war) zuordnen.

    Bricht beim ersten `NichtErreichbar` ab und laesst den Rest stehen: der
    naechste Versuch macht weiter, und ein halber Lauf ist schon festgeschrieben.
    """
    from app.models import Sache
    from app.services.sachen import isbn13

    offen = db.execute(select(Sache).where(Sache.bereich == BEREICH, Sache.titel_id.is_(None))
                       .order_by(Sache.id)).scalars().all()
    n = 0
    for s in offen:
        t = titel_holen(s.titel_huelle or s.name, s.medientyp, isbn13(s.barcode or ""))
        s.titel_id, s.name = int(t["id"]), t["titel"]
        s.medientyp = s.medientyp or t.get("medientyp")
        db.commit()
        n += 1
    if n:
        logger.info("medien_titel_nachgetragen", stuecke=n)
    return n


def ohne_titel(db: Session) -> int:
    from sqlalchemy import func

    from app.models import Sache

    return db.execute(select(func.count()).select_from(Sache).where(
        Sache.bereich == BEREICH, Sache.titel_id.is_(None))).scalar() or 0


# ---------------------------------------------------------------------------
# Spiegel
# ---------------------------------------------------------------------------

def abzug(db: Session) -> list[dict]:
    from app.models import Sache
    from app.services.plaetze import pfad

    # Abgegangenes fehlt im Abzug: medien behaelt dann seinen eigenen Abgang
    # (verkauft mit Erloes) oder bucht es als „Weg", wenn das Lager es ausgebucht hat.
    zeilen = db.execute(select(Sache).where(Sache.bereich == BEREICH, Sache.im_bestand())
                        .order_by(Sache.id)).scalars()
    return [{
        "kennung": s.kennung, "titel_id": s.titel_id, "name": s.name, "teil": s.teil,
        "edition": s.edition, "einband": s.einband, "medium": s.medium, "medientyp": s.medientyp,
        "zustand": s.condition, "verbleib": s.verbleib, "shopfloor_grund": s.shopfloor_grund,
        "platz": pfad(s.platz) or None, "einstand": s.purchase_price, "barcode": s.barcode,
        "foto": bool(s.foto),
    } for s in zeilen]


# medien schreibt den Abgang gross („Verkauft", „Weg"), das Lager klein.
ABGANG_AUS_MEDIEN = {"Verkauft": "verkauft", "Weg": "weg"}


def abgaenge_abholen(db: Session) -> int:
    """In medien gebuchte Abgaenge hier ausbuchen (Stufe 7a, vor jedem Abzug).

    Der Verkauf von Filmen gehoert medien (Owner). medien legt ihn unter
    `/api/lager/abgaenge` bereit, und die Richtung bleibt „nur das Lager ruft
    medien". Ausgebucht wird nur ein Stueck dieses Bereichs, das hier noch im
    Bestand steht; danach fehlt es im Abzug, und die Liste dort wird kuerzer.
    Ein unbekannter Abgangswert wird uebersprungen und geloggt, nicht geraten.
    """
    from app.models import Sache
    from app.services.electronics import ElectronicAssetService

    svc = ElectronicAssetService(db)
    n = 0
    for a in dict(_ruf("GET", "/api/lager/abgaenge")).get("abgaenge", []):
        abgang = ABGANG_AUS_MEDIEN.get(a.get("abgang") or "")
        s = db.execute(select(Sache).where(Sache.bereich == BEREICH, Sache.kennung == a.get("kennung"),
                                           Sache.im_bestand())).scalar_one_or_none()
        if s is None:
            continue
        if abgang is None:
            logger.warning("medien_abgang_unbekannt", kennung=s.kennung, abgang=a.get("abgang"))
            continue
        am = None
        try:
            am = date.fromisoformat(str(a.get("am"))[:10]) if a.get("am") else None
        except ValueError:
            pass
        erloes = a.get("erloes") if abgang == "verkauft" else None
        svc.abgang(s.id, abgang, am=am, erloes=float(erloes) if erloes is not None else None,
                   plattform=a.get("plattform"), aus_medien=True)
        n += 1
    if n:
        db.commit()
        logger.info("medien_abgaenge_abgeholt", stuecke=n)
    return n


def spiegel_senden() -> int:
    """Erst die Abgaenge aus medien holen, dann den ganzen Bestand des
    Katalog-Mandanten an medien schicken."""
    from app.db import SessionLocal

    db = SessionLocal()
    db.info["owner_sub"] = settings.DEFAULT_OWNER_SUB
    try:
        abgaenge_abholen(db)
        titel_nachtragen(db)
        stuecke = abzug(db)
    finally:
        db.close()
    _ruf("PUT", "/api/lager/bestand", json={
        "stand": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stuecke": stuecke})
    return len(stuecke)


_signal = threading.Event()
_laeufer: threading.Thread | None = None
_sperre = threading.Lock()


def _schleife() -> None:
    while True:
        if _signal.wait(_pause()):
            # Entprellen: ein Lauf schickt Scan um Scan, gesendet wird einmal.
            time.sleep(2)
        _signal.clear()
        try:
            n = spiegel_senden()
            verbindung.ok()
            logger.info("medien_spiegel_gesendet", stuecke=n)
        except DomainError as fehler:
            verbindung.gescheitert(str(fehler))
            logger.warning("medien_spiegel_fehlgeschlagen", grund=str(fehler),
                           naechster_versuch_s=_pause())
        except Exception as fehler:  # noqa: BLE001 - der Laeufer darf nie sterben
            verbindung.gescheitert(type(fehler).__name__)
            logger.exception("medien_spiegel_fehler")


def starten() -> None:
    """Beim Start: einmal sofort senden (nach einem Zurueckspielen ist der
    Spiegel in medien sonst bis zum ersten Takt alt), dann im Takt."""
    global _laeufer
    if not konfiguriert():
        return
    with _sperre:
        if _laeufer is None or not _laeufer.is_alive():
            _laeufer = threading.Thread(target=_schleife, name="medien-spiegel", daemon=True)
            _laeufer.start()
    _signal.set()


def anstossen() -> None:
    """Nach einer Aenderung: entprellt, blockiert die Anfrage nie."""
    if konfiguriert():
        starten()
