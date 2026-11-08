"""Der Loeschweg dieses Dienstes: welche Tabelle in welcher Reihenfolge faellt.

Die Mechanik liegt in ``konto_mechanik.py`` (dort auch, warum es hier keine
Netzroute gibt und wie die vier Kopien abgeglichen werden). Hier steht nur, was
dieser Dienst ueber seine eigenen Tabellen weiss.

    docker exec -w /app lager python -m app.konto --sub X [--loeschen]

DIE REIHENFOLGE IST NICHT FREI
================================

Alle Fremdschluessel dieses Dienstes tragen **kein** ``ondelete``, und
``PRAGMA foreign_keys=ON`` steht in ``db.py``. Ein Loeschen in falscher
Reihenfolge scheitert deshalb an der Datenbank, also mit einer Fehlermeldung
statt mit einer Aussage. Kinder zuerst:

    consumption_event -> stock_entry -> product
    stock_entry, sache -> platz  (platz haengt an sich selbst, faellt in einem Zug)
    stock_entry, sache -> einkauf
    verlauf           (haengt an nichts, bewusst ohne Fremdschluessel)

Das Mandanten-Scoping aus ``app/tenant.py`` greift hier **nicht**: es haengt
an ``do_orm_execute`` und prueft ``is_select``. Ein rohes ``DELETE`` laeuft
daran vorbei, deshalb steht die Mandantenbedingung in jedem Schritt ausdruecklich.
Das ist Absicht und keine Umgehung: ein Loeschweg, der sich auf einen
Select-Filter verlaesst, haette keinen.
"""

from __future__ import annotations

from app import konto_mechanik as mechanik

PLAN = mechanik.Plan(
    dienst="lager",
    schritte=(
        mechanik.eigene("consumption_event", warum="Verbrauchsereignisse"),
        mechanik.eigene("stock_entry", warum="Bestandsposten"),
        mechanik.eigene("sache", warum="Sachen: Technik-Stuecke, spaeter Werkstatt"),
        mechanik.eigene("product", warum="Produktstammdaten des Mandanten"),
        mechanik.eigene("platz", warum="Lagerplaetze und Kisten"),
        mechanik.eigene("einkauf", warum="Einkaeufe aus dem Einbuch-Lauf"),
        mechanik.eigene("verlauf", warum="Aenderungsverlauf je Feld"),
    ),
)

def foto_dateien(db, sub: str) -> list:
    """Die Fotos der Sachen dieses Mandanten.

    Gesammelt VOR den Loeschschritten und erst nach dem Commit vollzogen
    (`konto_mechanik.ausfuehren`): danach nennt keine Zeile mehr einen Namen,
    und ein Foto ohne Zeile waere ein Bild aus einem geloeschten Konto, das
    niemand mehr findet.
    """
    from sqlalchemy import text

    from app.services import fotos

    namen = db.execute(
        text("SELECT foto FROM sache WHERE owner_sub = :s AND foto IS NOT NULL"), {"s": sub}
    ).scalars().all()
    return [p for p in (fotos.pfad_fuer(n) for n in namen) if p is not None]


# Gegenprobe gegen die zweite Liste, die es in diesem Dienst schon gibt:
# ``app/tenant.py`` fuehrt ``TENANT_MODELS`` fuer das Select-Scoping. Beide
# Listen beschreiben dasselbe ("was gehoert einem Mandanten"), und wenn sie
# auseinanderlaufen, ist entweder das Scoping undicht oder der Loeschweg
# unvollstaendig. Geprueft wird in ``tests/test_konto_loeschplan.py``.


if __name__ == "__main__":
    from app import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from app.db import Base, SessionLocal

    raise SystemExit(mechanik.als_programm(PLAN, Base.metadata, SessionLocal,
                                          dateien=foto_dateien))
