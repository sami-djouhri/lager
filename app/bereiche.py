"""Die Bereiche des Lagers und der eine Satz je Bereich für die Startseite.

Die Liste ist fest (Entscheid 2026-11-01: „nur feste Bereiche"),
Begründung und Stufen in `RICHTUNG.md`. Sie steht hier und sonst nirgends:
das Frontend holt sie über `/api/bereiche`, statt eine zweite Liste zu führen.

Jeder Bereich hat eine **Bauart**, und nur die entscheidet über die Logik:

* ``vorrat``: Menge, Frist, Mindestbestand (Produkte + Posten, wie bisher)
* ``stueck``: Einzelstück mit Nummer, Wert und Verkaufsschutz
* ``fundort``: wo es liegt, ohne Menge (Stufe 6)
* ``kiste``: nur Kisten mit Inhaltsangabe (Kisten sind Plaetze, `app/services/plaetze.py`)
* ``exemplar``: Einzelstueck zu einem Titel im medien-Katalog (Filme & Medien, Stufe 5)

Ein Bereich, dessen Bauart noch nicht gebaut ist, kommt mit ``bereit: False``
und der Stufe, die ihn öffnet. Eine Kachel, die in eine leere Seite führt, sähe
aus wie ein kaputter Bereich.

Die Sätze rechnet der Server, mit fester Rangfolge im Code: was blockiert,
steht vorn (Vorbild `medien/app/dashboard.py`). Eine Rangfolge im Browser wäre
eine, die kein Test prüft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import DomainError
from app.models import SHOPFLOOR_GRUENDE, Platz, Product, Sache, StockEntry
from app.services.electronics import (
    AUSBUCHEN_NACH_TAGEN,
    lange_vermisst,
    verkauf_empfohlen,
    vermisst_seit,
)
from app.services.stats import StatsService

VORRAT = "vorrat"
STUECK = "stueck"
FUNDORT = "fundort"
KISTE = "kiste"
EXEMPLAR = "exemplar"
# Bauarten, deren Dinge `sache`-Zeilen sind (Kennung, Platz, Verbleib, Foto).
SACHEN_BAUARTEN = (STUECK, EXEMPLAR)

STANDARD = "lebensmittel"


@dataclass(frozen=True)
class Bereich:
    schluessel: str
    name: str
    bauart: str
    # Wie die Frist in diesem Bereich heißt; None = keine Frist vorgesehen.
    frist: str | None = None
    # Wie ein Posten über der Frist heißt („abgelaufen", „nicht mehr keimfähig").
    vorbei: str = "abgelaufen"
    # Stufe aus RICHTUNG.md, die den Bereich öffnet; None = gebaut.
    stufe: int | None = None
    # Ortsvorschläge für Aufrufer, die noch keinen Platz wählen (Lager-App
    # 0.1.0 bucht damit ein, `PlatzService.aus_ortstext`). Das Web wählt Plätze.
    orte: tuple[str, ...] = ()
    # Vorschläge für die Kategorie (Filter-Chips und Formular). Frei bleibt sie
    # trotzdem: ein Altbestand mit eigener Kategorie fällt nicht heraus.
    kategorien: tuple[str, ...] = ()
    # Shopfloor-Gruende dieses Bereichs (Schluessel aus `models.SHOPFLOOR_GRUENDE`).
    # Owner 2026-11-01: je Bereich, Filme mit Rippen und Schauen wie in medien.
    gruende: tuple[str, ...] = ()


BEREICHE: tuple[Bereich, ...] = (
    Bereich("lebensmittel", "Lebensmittel", VORRAT, frist="MHD", vorbei="über dem MHD",
            orte=("Vorratskammer", "Kühlschrank", "Tiefkühler"),
            kategorien=("Getreide", "Milchprodukte", "Fleisch", "Gemüse", "Obst", "Gewürze",
                        "Öle", "Konserven", "Sonstiges")),
    Bereich("getraenke", "Getränke & Keller", VORRAT, frist="MHD", vorbei="über dem MHD",
            orte=("Keller", "Kühlschrank", "Vorratskammer"),
            kategorien=("Wasser", "Saft & Limo", "Bier", "Wein & Sekt", "Spirituosen",
                        "Kaffee & Tee", "Sonstiges")),
    Bereich("haushalt", "Haushalt & Drogerie", VORRAT,
            orte=("Abstellraum", "Bad", "Küche", "Keller"),
            kategorien=("Putzmittel", "Waschmittel", "Körperpflege", "Papier & Hygiene",
                        "Batterien & Leuchtmittel", "Sonstiges")),
    Bereich("apotheke", "Hausapotheke", VORRAT, frist="Verfall", vorbei="verfallen",
            orte=("Hausapotheke", "Bad", "Kühlschrank"),
            kategorien=("Schmerz & Fieber", "Erkältung", "Verbandsmaterial", "Magen & Darm",
                        "Haut", "Sonstiges")),
    Bereich("garten", "Garten & Saatgut", VORRAT, frist="Keimfähig bis",
            vorbei="nicht mehr keimfähig", orte=("Gartenhaus", "Keller", "Abstellraum"),
            kategorien=("Saatgut", "Dünger", "Erde & Substrat", "Pflanzenschutz", "Sonstiges")),
    Bereich("werkstatt", "Werkstatt-Material", FUNDORT, stufe=6),
    Bereich("technik", "Technik & Sachen", STUECK,
            gruende=("im_einsatz", "reparatur", "verkauf_vorbereiten")),
    # Der Titel kommt live aus medien (RICHTUNG.md „Filme & Medien"). Offen ist
    # der Bereich nur, wenn die Anbindung steht und der Mandant der ist, dem der
    # Katalog gehoert (medien ist einbenutzig); sonst ausgegraut mit einem Satz.
    Bereich("medien", "Filme & Medien", EXEMPLAR,
            gruende=("rippen", "schauen", "verkauf_vorbereiten")),
    Bereich("kleidung", "Kleidung & Schuhe", KISTE),
    Bereich("saison", "Saison & Deko", KISTE),
)

NACH_SCHLUESSEL = {b.schluessel: b for b in BEREICHE}
VORRAT_SCHLUESSEL = frozenset(b.schluessel for b in BEREICHE if b.bauart == VORRAT)

STUFEN_NAMEN = {6: "Werkstatt-Material"}

# Ab wie vielen Tagen Restfrist ein Posten „bald" abläuft. Gleiche Grenze wie
# `StatsService.expiry_forecast` (kritisch <= 2, bald <= 7).
BALD_TAGE = 7


def _anzahl(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def _satz(schluessel: str, text: str, anzahl: int = 0, blockiert: bool = False) -> dict:
    return {"schluessel": schluessel, "text": text, "anzahl": anzahl, "blockiert": blockiert}


def _vorrat_satz(db: Session, b: Bereich) -> dict:
    heute = date.today()
    posten = db.execute(
        select(StockEntry.mhd)
        .join(Product, StockEntry.product_id == Product.id)
        .where(StockEntry.quantity > 0, Product.bereich == b.schluessel)
    ).scalars().all()
    if not posten:
        # Seit Stufe 4 legt der Einbuch-Lauf ein unbekanntes Produkt gleich
        # mit an; vorher fuehrte „kommt über Einbuchen" in einem frischen
        # Bereich in ein Formular ohne Auswahl.
        hat_produkte = db.execute(
            select(Product.id).where(Product.bereich == b.schluessel).limit(1)
        ).first()
        if hat_produkte:
            return _satz("leer", "Nichts auf Lager. Posten kommen über Einbuchen herein.")
        return _satz("leer", "Noch leer. Beim Einbuchen entstehen die Produkte gleich mit.")

    vorbei = sum(1 for m in posten if m is not None and m < heute)
    if vorbei:
        verb = "ist" if vorbei == 1 else "sind"
        return _satz("vorbei", f"{_anzahl(vorbei, 'Posten', 'Posten')} {verb} {b.vorbei}.",
                     vorbei, blockiert=True)

    bald = sum(1 for m in posten if m is not None and (m - heute).days <= BALD_TAGE)
    if bald:
        verb = "läuft" if bald == 1 else "laufen"
        return _satz("bald", f"{_anzahl(bald, 'Posten', 'Posten')} {verb} in den "
                     f"nächsten {BALD_TAGE} Tagen ab.", bald)

    # Mindestbestand: dieselbe Rechnung wie /api/stats/low-stock, je Bereich.
    knapp = len(StatsService(db).low_stock(bereich=b.schluessel))
    if knapp:
        verb = "liegt" if knapp == 1 else "liegen"
        return _satz("knapp", f"{_anzahl(knapp, 'Produkt', 'Produkte')} {verb} unter "
                     "dem Mindestbestand.", knapp)

    n = len(posten)
    rest = ", nichts läuft bald ab." if b.frist else ", nichts ist knapp."
    return _satz("ruhig", f"{_anzahl(n, 'Posten', 'Posten')}{rest}", n)


def _vermisst_satz(db: Session, stuecke: list[Sache]) -> dict | None:
    """Vermisst steht vor Verkauf und Einlagern (Stufe 7a): was fehlt, ist
    die Frage, die nur der Owner beantworten kann, und blockiert deshalb.
    Fehlt ein Stück seit `AUSBUCHEN_NACH_TAGEN`, fragt der Satz nach dem Ausbuchen."""
    n = sum(1 for s in stuecke if s.verbleib == "vermisst")
    if not n:
        return None
    lange = sum(1 for t in vermisst_seit(db, stuecke).values() if lange_vermisst(t))
    if lange:
        verb = "fehlt" if lange == 1 else "fehlen"
        return _satz("vermisst_lange", f"{_anzahl(lange, 'Stück', 'Stücke')} {verb} seit über "
                     f"{AUSBUCHEN_NACH_TAGEN} Tagen. Als weg ausbuchen?", lange, blockiert=True)
    verb = "ist" if n == 1 else "sind"
    return _satz("vermisst", f"{_anzahl(n, 'Stück', 'Stücke')} {verb} vermisst.", n, blockiert=True)


def _stueck_satz(db: Session) -> dict:
    stuecke = db.execute(select(Sache).where(Sache.bereich == "technik", Sache.im_bestand())
                         ).scalars().all()
    if not stuecke:
        return _satz("leer", "Noch keine Stücke erfasst.")
    vermisst = _vermisst_satz(db, stuecke)
    if vermisst:
        return vermisst
    lohnend = sum(1 for a in stuecke if verkauf_empfohlen(a))
    if lohnend:
        verb = "lohnt" if lohnend == 1 else "lohnen"
        return _satz("verkauf", f"{_anzahl(lohnend, 'Stück', 'Stücke')} {verb} den Verkauf.",
                     lohnend)
    aktiv = sum(1 for a in stuecke if a.in_active_use)
    return _satz("ruhig", f"{_anzahl(len(stuecke), 'Stück', 'Stücke')}, "
                 f"{aktiv} davon im Einsatz.", len(stuecke))


def _exemplar_satz(db: Session, b: Bereich) -> dict:
    stuecke = db.execute(select(Sache).where(Sache.bereich == b.schluessel, Sache.im_bestand())
                         ).scalars().all()
    if not stuecke:
        return _satz("leer", "Noch nichts eingebucht. Der Titel kommt beim Einbuchen aus medien.")
    # Die Verbindung zu medien vor allem anderen: solange sie fehlt, stimmt
    # die Fehlt-Liste dort nicht, und Stuecke ohne Titel zaehlt medien gar nicht.
    from app.services import medien

    ohne = sum(1 for s in stuecke if s.titel_id is None)
    if medien.verbindung.fehler_seit is not None:
        seit = medien.verbindung.fehler_seit.astimezone().strftime("%H:%M")
        rest = f" {_anzahl(ohne, 'Stück wartet', 'Stücke warten')} auf den Titel." if ohne else ""
        return _satz("getrennt", f"medien antwortet seit {seit} Uhr nicht.{rest}", ohne)
    if ohne:
        return _satz("ohne_titel", f"{_anzahl(ohne, 'Stück wartet', 'Stücke warten')} auf den "
                     "Titel aus medien.", ohne)
    vermisst = _vermisst_satz(db, stuecke)
    if vermisst:
        return vermisst
    offen = sum(1 for s in stuecke if s.verbleib == "shopfloor" and s.shopfloor_grund is None)
    if offen:
        verb = "wartet" if offen == 1 else "warten"
        return _satz("einlagern", f"{_anzahl(offen, 'Stück', 'Stücke')} {verb} aufs Einlagern.",
                     offen)
    return _satz("ruhig", f"{_anzahl(len(stuecke), 'Stück', 'Stücke')}, alle an ihrem Platz.",
                 len(stuecke))


def _kisten_satz(db: Session, b: Bereich) -> dict:
    kisten = db.execute(
        select(Platz.inhalt).where(Platz.art == "kiste", Platz.bereich == b.schluessel)
    ).scalars().all()
    if not kisten:
        return _satz("leer", "Noch keine Kiste. Kisten stehen an einem Platz und tragen ihren Inhalt.")
    ohne = sum(1 for i in kisten if not (i or "").strip())
    if ohne:
        verb = "hat" if ohne == 1 else "haben"
        return _satz("ohne_inhalt", f"{_anzahl(ohne, 'Kiste', 'Kisten')} {verb} noch "
                     "keine Inhaltsangabe.", ohne)
    return _satz("ruhig", f"{_anzahl(len(kisten), 'Kiste', 'Kisten')}, alle beschriftet.",
                 len(kisten))


def uebersicht(db: Session) -> list[dict]:
    """Alle Bereiche in fester Reihenfolge, je mit genau einem Satz."""
    from app.services import medien

    aus: list[dict] = []
    for b in BEREICHE:
        bereit = b.stufe is None
        if b.stufe is not None:
            satz = _satz("stufe", f"Kommt mit Stufe {b.stufe}: {STUFEN_NAMEN[b.stufe]}.")
        elif b.bauart == EXEMPLAR and not medien.offen(db):
            bereit = False
            satz = _satz("ohne_katalog", medien.warum_zu(db))
        elif b.bauart == EXEMPLAR:
            satz = _exemplar_satz(db, b)
        elif b.bauart == VORRAT:
            satz = _vorrat_satz(db, b)
        elif b.bauart == KISTE:
            satz = _kisten_satz(db, b)
        else:
            satz = _stueck_satz(db)
        aus.append({
            "schluessel": b.schluessel,
            "name": b.name,
            "bauart": b.bauart,
            "frist": b.frist,
            "orte": list(b.orte),
            "kategorien": list(b.kategorien),
            "bereit": bereit,
            "gruende": [{"schluessel": g, "name": SHOPFLOOR_GRUENDE[g]} for g in b.gruende],
            "satz": satz,
            # Filme & Medien: Verweis auf den Titel, `{titel_id}` setzt die Oberflaeche ein.
            "titel_verweis": (f"{settings.MEDIEN_WEB_URL.rstrip('/')}/#titel/{{titel_id}}"
                              if b.bauart == EXEMPLAR and settings.MEDIEN_WEB_URL else None),
        })
    return aus


def gruende_fuer(schluessel: str) -> tuple[str, ...]:
    b = NACH_SCHLUESSEL.get(schluessel)
    return b.gruende if b else ()


def pruefe_vorrat(schluessel: str) -> str:
    """Ein Bereich, in dem Produkte liegen dürfen, sonst DomainError."""
    if schluessel not in VORRAT_SCHLUESSEL:
        raise DomainError(
            f"Bereich '{schluessel}' führt keine Produkte",
            {"erlaubt": sorted(VORRAT_SCHLUESSEL)},
        )
    return schluessel
