"""Ein Foto je Sache: ablegen, ausliefern, loeschen (Vorbild `medien/app/bilder.py`).

Owner 2026-11-01: Fotos gelten fuer **alle Sachen** (Technik, spaeter Werkstatt
und Medien), nicht fuer Vorraete. Aufgenommen im Einbuch-Lauf aus dem laufenden
Kamerastrom, am Schreibtisch ueber die Dateiauswahl.

Nur JPEG, geprueft an den Magic-Bytes und nicht am `Content-Type`: was hier
hereinkommt, wird wieder ausgeliefert. Eine SVG- oder HTML-Datei unter dem Namen
eines Bildes waere ein Skript auf der eigenen Herkunft. Die Auslieferung traegt
deshalb zusaetzlich `nosniff` und einen festen Typ.

Die Dateien liegen im Volume `lager-data` unter `fotos/`, neben der
Datenbank, und werden mit ihm gesichert. Nach einem Zurueckspielen ohne Volume
steht der Name in der Zeile und die Datei fehlt: die Ausliefer-Route antwortet
dann 404, die Oberflaeche zeigt kein Bild. Sichtbar, nicht kaputt.

Geloescht wird eine Datei erst NACH dem Commit, der sie aus der Zeile nimmt.
Ein Dateisystem-Eingriff in einer offenen Transaktion waere verloren, wenn sie
zurueckrollt, und dann zeigte die Zeile auf eine Datei, die es nicht mehr gibt.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from app.logging import get_logger

logger = get_logger(__name__)

MAX_BYTES = 4 * 1024 * 1024
JPEG_KOPF = b"\xff\xd8\xff"
# Der Name kommt aus der eigenen Datenbank, nie aus der Anfrage. Die Pruefung an
# der Stelle, die den Pfad bildet, haelt trotzdem, falls das Feld einmal von
# Hand gefuellt wird.
NAME_MUSTER = re.compile(r"^sache-\d+-\d+\.jpg$")


class UngueltigesBild(ValueError):
    """Die Daten sind kein JPEG oder zu gross."""


def verzeichnis() -> Path:
    # Zur Laufzeit gelesen, nicht beim Import: die Tests setzen eine eigene
    # Ablage, und ein beim Import eingefrorener Pfad schriebe in die echte.
    return Path(os.environ.get("LAGER_FOTO_DIR", "/app/data/fotos"))


def _pfad(name: str) -> Path | None:
    if not name or not NAME_MUSTER.match(name):
        return None
    return verzeichnis() / name


def pruefen(rohdaten: bytes) -> None:
    if not rohdaten:
        raise UngueltigesBild("Leere Daten")
    if len(rohdaten) > MAX_BYTES:
        raise UngueltigesBild(
            f"Bild zu groß ({len(rohdaten) // 1024} KB, erlaubt {MAX_BYTES // 1024} KB)")
    if not rohdaten.startswith(JPEG_KOPF):
        raise UngueltigesBild("Nur JPEG. Die Oberfläche wandelt jedes Kamerabild um.")


def speichern(sache_id: int, rohdaten: bytes, stempel: int) -> str:
    """Ablegen und den Dateinamen zurueckgeben.

    Der Millisekunden-`stempel` steht im Namen, damit ein ersetztes Foto eine
    neue Adresse bekommt; sonst zeigte der Browser sein Altbild aus dem Cache,
    und das saehe aus wie ein fehlgeschlagenes Hochladen.
    """
    pruefen(rohdaten)
    verzeichnis().mkdir(parents=True, exist_ok=True)
    name = f"sache-{int(sache_id)}-{int(stempel)}.jpg"
    ziel = verzeichnis() / name
    # Daneben schreiben, dann umbenennen: ein abgebrochener Upload liesse sonst
    # eine halbe Datei unter einem Namen liegen, der schon in der Zeile steht.
    vorlaeufig = ziel.with_suffix(".jpg.teil")
    vorlaeufig.write_bytes(rohdaten)
    vorlaeufig.replace(ziel)
    return name


def datei(name: str | None) -> Path | None:
    pfad = _pfad(name or "")
    return pfad if pfad and pfad.is_file() else None


def pfad_fuer(name: str | None) -> Path | None:
    """Der Pfad, auch wenn die Datei fehlt (fuer den Loeschweg eines Mandanten)."""
    return _pfad(name or "")


def loeschen(name: str | None) -> bool:
    pfad = _pfad(name or "")
    if not pfad:
        return False
    try:
        pfad.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        # Ein nicht loeschbares Bild darf den Vorgang nicht abbrechen, der es
        # loeschen wollte. Es bleibt liegen und wird gemeldet.
        logger.exception("foto_loeschen_fehlgeschlagen", name=name)
        return False
