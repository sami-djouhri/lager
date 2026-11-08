"""Lagerplaetze: Raum › Regal › Fach › Kiste, Etiketten-Kennung, Verlauf.

Die Verschachtelung ist fest (Owner 2026-11-01, `RICHTUNG.md`
„Architektur"): ein Regal steht in einem Raum, ein Fach in einem Regal, eine
Kiste in einem Fach oder direkt im Raum, **nie in einer Kiste**. Dinge duerfen
an jeder Ebene liegen. Zieht eine Kiste um, aendert sich nur ihr Eltern-Platz,
der Inhalt zieht ohne eine Buchung mit.

Die Kennung `L-001` ist fortlaufend je Mandant und NICHT aus dem Namen
abgeleitet (ein Etikett klebt, ein Name wird umbenannt). Sie wird auch nach
dem Loeschen nie neu vergeben: der geloeschte Platz hinterlaesst sie im
Verlauf, und `_naechste_kennung` zaehlt dort mit.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import DomainError
from app.models import Platz, Sache, StockEntry, Verlauf

ARTEN = ("raum", "regal", "fach", "kiste")
ART_NAMEN = {"raum": "Raum", "regal": "Regal", "fach": "Fach", "kiste": "Kiste"}

# Welche Art in welcher stehen darf. None = ganz oben.
ELTERN_ERLAUBT: dict[str, tuple[str | None, ...]] = {
    "raum": (None,),
    "regal": ("raum",),
    "fach": ("regal",),
    "kiste": ("raum", "fach"),
}

TRENNER = " › "


def protokolliere(db: Session, ziel: str, ziel_id: int, feld: str, alt, neu) -> None:
    """Eine Zeile Verlauf, nur wenn sich wirklich etwas aendert."""
    alt_t = None if alt is None else str(alt)
    neu_t = None if neu is None else str(neu)
    if alt_t == neu_t:
        return
    db.add(Verlauf(ziel=ziel, ziel_id=ziel_id, feld=feld, alt=alt_t, neu=neu_t))


def pfad(platz: Platz | None) -> str:
    """„Keller › Regal A › Fach 2". Leer, wenn kein Platz."""
    teile: list[str] = []
    p = platz
    while p is not None and len(teile) < len(ARTEN):
        teile.append(p.name)
        p = p.eltern
    return TRENNER.join(reversed(teile))


def ortstext(platz: Platz | None) -> str:
    """Der alte Ortstext fuer `location` (Lager-App 0.1.0, life-ops).

    Nur der Name, nicht der Pfad: die App filtert Posten nach
    `location == ort` mit den Ortsvorschlaegen des Bereichs.
    """
    return platz.name if platz is not None else "nicht eingelagert"


def falte(text: str) -> str:
    """Fuer Vergleiche: klein, Umlaute ausgeschrieben, Raender weg."""
    t = text.strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return t


class PlatzService:
    def __init__(self, db: Session):
        self.db = db

    # ----- lesen -----

    def alle(self) -> list[Platz]:
        return list(self.db.execute(select(Platz).order_by(Platz.name)).scalars().all())

    def get(self, platz_id: int) -> Platz:
        platz = self.db.get(Platz, platz_id)
        if platz is None:
            raise DomainError("Platz nicht gefunden", {"platz_id": platz_id})
        return platz

    def per_kennung(self, kennung: str) -> Platz | None:
        m = re.fullmatch(r"\s*L[:-]?(\d{1,6})\s*", kennung, re.I)
        if not m:
            return None
        k = f"L-{int(m.group(1)):03d}"
        return self.db.execute(select(Platz).where(Platz.kennung == k)).scalar_one_or_none()

    def belegung(self) -> dict[int, dict[str, int]]:
        """Je Platz: Zahl der Kinder, Posten (mit Menge) und Sachen."""
        aus: dict[int, dict[str, int]] = {}

        def zaehle(stmt, schluessel: str) -> None:
            for pid, n in self.db.execute(stmt).all():
                if pid is not None:
                    aus.setdefault(pid, {"kinder": 0, "posten": 0, "sachen": 0})[schluessel] = n

        zaehle(select(Platz.eltern_id, func.count()).group_by(Platz.eltern_id), "kinder")
        zaehle(
            select(StockEntry.platz_id, func.count())
            .where(StockEntry.quantity > 0)
            .group_by(StockEntry.platz_id),
            "posten",
        )
        zaehle(select(Sache.platz_id, func.count()).where(Sache.im_bestand())
               .group_by(Sache.platz_id), "sachen")
        return aus

    # ----- schreiben -----

    def anlegen(
        self,
        *,
        name: str,
        art: str,
        eltern_id: int | None = None,
        inhalt: str | None = None,
        bereich: str | None = None,
    ) -> Platz:
        name = (name or "").strip()
        if not name:
            raise DomainError("Name fehlt", {})
        if art not in ARTEN:
            raise DomainError(f"Unbekannte Art '{art}'", {"erlaubt": list(ARTEN)})
        eltern = self._pruefe_eltern(art, eltern_id)
        self._pruefe_kistenfelder(art, inhalt, bereich)
        platz = Platz(
            kennung=self._naechste_kennung(),
            name=name,
            art=art,
            eltern_id=eltern.id if eltern else None,
            inhalt=(inhalt or None) if art == "kiste" else None,
            bereich=bereich if art == "kiste" else None,
        )
        self.db.add(platz)
        self.db.flush()
        protokolliere(self.db, "platz", platz.id, "angelegt", None, platz.kennung)
        return platz

    def aendern(self, platz_id: int, felder: dict) -> Platz:
        """Nur die mitgegebenen Felder. `eltern_id` = umziehen."""
        platz = self.get(platz_id)
        if "name" in felder:
            name = (felder["name"] or "").strip()
            if not name:
                raise DomainError("Name fehlt", {})
            protokolliere(self.db, "platz", platz.id, "name", platz.name, name)
            platz.name = name
        if "eltern_id" in felder:
            eltern = self._pruefe_eltern(platz.art, felder["eltern_id"])
            neu = eltern.id if eltern else None
            protokolliere(self.db, "platz", platz.id, "eltern_id", platz.eltern_id, neu)
            platz.eltern_id = neu
            platz.eltern = eltern
        if platz.art == "kiste":
            inhalt = felder.get("inhalt", platz.inhalt)
            bereich = felder.get("bereich", platz.bereich)
            self._pruefe_kistenfelder("kiste", inhalt, bereich)
            protokolliere(self.db, "platz", platz.id, "inhalt", platz.inhalt, inhalt or None)
            protokolliere(self.db, "platz", platz.id, "bereich", platz.bereich, bereich)
            platz.inhalt = inhalt or None
            platz.bereich = bereich
        elif felder.get("inhalt") or felder.get("bereich"):
            raise DomainError("Inhalt und Bereich gibt es nur an einer Kiste", {"art": platz.art})
        self.db.flush()
        return platz

    def loeschen(self, platz_id: int) -> None:
        """Nur ein leerer Platz. Etwas still auf den Shopfloor zu schieben,
        haette ein Fach voller Dinge mit einem Klick unauffindbar gemacht."""
        platz = self.get(platz_id)
        b = self.belegung().get(platz.id, {})
        if any(b.values()):
            raise DomainError(
                f"{ART_NAMEN[platz.art]} „{platz.name}“ ist nicht leer",
                {"kinder": b.get("kinder", 0), "posten": b.get("posten", 0),
                 "sachen": b.get("sachen", 0)},
            )
        # Leere Posten (Menge 0) behalten ihre Geschichte, verlieren nur den Platz.
        for e in self.db.execute(select(StockEntry).where(StockEntry.platz_id == platz.id)).scalars():
            e.platz_id = None
        # Abgegangene Sachen zaehlen nicht als Belegung, behalten aber den Platz
        # fuer ein Zuruecknehmen; mit dem Platz geht das, sie kaemen auf den Shopfloor.
        for s in self.db.execute(select(Sache).where(Sache.platz_id == platz.id)).scalars():
            s.platz_id = None
            if s.verbleib == "eingelagert":
                s.verbleib = "shopfloor"
        protokolliere(self.db, "platz", platz.id, "geloescht", platz.kennung, None)
        self.db.delete(platz)
        self.db.flush()

    def aus_ortstext(self, text: str | None) -> Platz | None:
        """Uebergang fuer Aufrufer, die noch einen freien Ortstext schicken.

        Die Lager-App 0.1.0 bucht mit `location` aus den Ortsvorschlaegen
        des Bereichs ein. Bis sie `platz_id` kennt, wird der Text auf einen
        Platz gleichen Namens gelegt, und fehlt der, entsteht ein Raum. Ein
        Ablehnen haette das Einbuchen am Telefon gebrochen.
        """
        name = (text or "").strip()
        # „Elektronik" und „Homelab" waren Vorgaben fuer Stuecke, keine Orte.
        if not name or name.lower() in {"nicht eingelagert", "shopfloor", "elektronik", "homelab"}:
            return None
        # Gefaltet verglichen: die Altorte heissen seit der Migration
        # „Kuehlschrank", die App schickt „Kühlschrank". Ohne das entstuende
        # beim ersten Einbuchen am Telefon ein zweiter Raum.
        gesucht = falte(name)
        treffer = next((p for p in self.db.execute(select(Platz).order_by(Platz.id)).scalars()
                        if falte(p.name) == gesucht), None)
        return treffer or self.anlegen(name=name, art="raum")

    # ----- intern -----

    def _naechste_kennung(self) -> str:
        hoechste = 0
        kennungen = list(self.db.execute(select(Platz.kennung)).scalars())
        kennungen += list(self.db.execute(
            select(Verlauf.alt).where(Verlauf.ziel == "platz", Verlauf.feld == "geloescht")
        ).scalars())
        for k in kennungen:
            m = re.fullmatch(r"L-(\d+)", k or "")
            if m:
                hoechste = max(hoechste, int(m.group(1)))
        return f"L-{hoechste + 1:03d}"

    def _pruefe_eltern(self, art: str, eltern_id: int | None) -> Platz | None:
        eltern = self.get(eltern_id) if eltern_id is not None else None
        erlaubt = ELTERN_ERLAUBT[art]
        if (eltern.art if eltern else None) not in erlaubt:
            namen = " oder ".join("ganz oben" if e is None else f"in einem {ART_NAMEN[e]}"
                                  for e in erlaubt)
            raise DomainError(
                f"Ein {ART_NAMEN[art]} steht {namen}",
                {"art": art, "eltern_art": eltern.art if eltern else None},
            )
        return eltern

    @staticmethod
    def _pruefe_kistenfelder(art: str, inhalt: str | None, bereich: str | None) -> None:
        # Spaet importiert: app.bereiche liest ueber die Statistik diesen Dienst mit.
        from app.bereiche import KISTE, NACH_SCHLUESSEL

        if art != "kiste":
            if inhalt or bereich:
                raise DomainError("Inhalt und Bereich gibt es nur an einer Kiste", {"art": art})
            return
        if bereich is not None and (
            bereich not in NACH_SCHLUESSEL or NACH_SCHLUESSEL[bereich].bauart != KISTE
        ):
            erlaubt = sorted(k for k, b in NACH_SCHLUESSEL.items() if b.bauart == KISTE)
            raise DomainError(f"Bereich '{bereich}' fuehrt keine Kisten", {"erlaubt": erlaubt})
