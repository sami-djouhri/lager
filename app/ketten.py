"""Die Ladenketten fuer den Preisvergleich der Einkaufsliste (Owner 2026-11-07).

Beim Abschluss eines Einbuch-Laufs wird der Laden einmal je Einkauf gewaehlt:
eine der fuenf Ketten per Logo oder „Sonstiger" mit Freitext. Nur ein Einkauf
mit Kette zaehlt fuer den Tiefstpreis (``/api/preise``, ``je_kette``); ein
Freitext-Laden bleibt am Einkauf stehen, vergleicht aber nichts.

Ein Freitext, der den Kettennamen enthaelt („Kaufland Mitte"), wird der Kette
zugeordnet. So hat es auch die Migration 0012 mit dem Altbestand gemacht.
"""

from __future__ import annotations

KETTEN: dict[str, str] = {
    "kaufland": "Kaufland",
    "lidl": "Lidl",
    "netto": "Netto",
    "akzenta": "Akzenta",
    "picnic": "Picnic",
}


def kette_aus_name(name: str | None) -> str | None:
    text = (name or "").casefold()
    for schluessel in KETTEN:
        if schluessel in text:
            return schluessel
    return None
