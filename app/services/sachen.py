"""Stueck-Kennung `S-0001` und das Lesen eines Scans.

Am Praefix erkennt der Scanner ohne Rueckfrage, was vor der Kamera war
(RICHTUNG.md): `L-` ist ein Platz, `S-` ein Stueck, alles andere ein
Strichcode (Sorte) oder eine Seriennummer (ein Geraet). Die Kennung wird
deshalb **vor** jeder anderen Deutung geprueft: `L-7` darf nie als
Strichcode durchgehen, sonst entstuende ein Produkt namens „L-7".

Die Kennung ist fortlaufend je Mandant und wird nie neu vergeben, auch
nicht nach dem Loeschen (der Verlauf behaelt sie, `feld="geloescht"`), aus
demselben Grund wie bei den Plaetzen: ein Etikett klebt.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Sache, Verlauf

_PLATZ = re.compile(r"\s*L[:-]?(\d{1,6})\s*", re.I)
_SACHE = re.compile(r"\s*S[:-]?(\d{1,6})\s*", re.I)


def platzkennung(code: str) -> str | None:
    m = _PLATZ.fullmatch(code or "")
    return f"L-{int(m.group(1)):03d}" if m else None


def sachkennung(code: str) -> str | None:
    m = _SACHE.fullmatch(code or "")
    return f"S-{int(m.group(1)):04d}" if m else None


def ist_strichcode(code: str) -> bool:
    """EAN-8, UPC-A, EAN-13, GTIN-14: nur Ziffern in diesen Laengen.

    Alles andere (Buchstaben, andere Laengen) ist eine Seriennummer. Die
    Unterscheidung zaehlt, weil eine Seriennummer genau ein Geraet meint und ein
    Strichcode eine Sorte: zwei gleiche USB-Sticks tragen denselben.
    """
    z = (code or "").strip()
    return z.isdigit() and len(z) in (8, 12, 13, 14)


def isbn13(code: str) -> str | None:
    """Eine ISBN (10 oder 13, mit Bindestrichen) als ISBN-13, sonst None.

    Dieselbe Pruefung wie medien `isbn.normalisieren`. Gebraucht wird sie, weil
    eine eingetippte „3-499-22660-X" kein Strichcode ist und sonst als
    Seriennummer gebucht wuerde; eine EAN ohne 978/979 ist kein Buch.
    """
    z = re.sub(r"[\s-]", "", code or "").upper()
    if len(z) == 10 and z[:9].isdigit() and (z[9].isdigit() or z[9] == "X"):
        if sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(z)) % 11:
            return None
        z = "978" + z[:9]
        return z + str((10 - sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(z)) % 10) % 10)
    if len(z) == 13 and z.isdigit() and z[:3] in ("978", "979"):
        if sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(z)) % 10:
            return None
        return z
    return None


def naechste_kennung(db: Session) -> str:
    """Fortlaufend je Mandant. Das Scoping in `app/tenant.py` schraenkt beide
    Abfragen auf den Mandanten der Sitzung ein."""
    hoechste = 0
    kennungen = list(db.execute(select(Sache.kennung)).scalars())
    kennungen += list(db.execute(
        select(Verlauf.alt).where(Verlauf.ziel == "sache", Verlauf.feld == "geloescht")
    ).scalars())
    # Auch was in dieser Sitzung angelegt, aber noch nicht geschrieben ist:
    # ein Lauf legt mehrere Sachen in einem Zug an.
    kennungen += [o.kennung for o in db.new if isinstance(o, Sache)]
    for k in kennungen:
        m = re.fullmatch(r"S-(\d+)", k or "")
        if m:
            hoechste = max(hoechste, int(m.group(1)))
    return f"S-{hoechste + 1:04d}"


def per_kennung(db: Session, kennung: str) -> Sache | None:
    k = sachkennung(kennung)
    if not k:
        return None
    return db.execute(select(Sache).where(Sache.kennung == k)).scalar_one_or_none()
