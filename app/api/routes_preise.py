"""Letzter Preis je Einheit je Produkt, fuer die Kostenschaetzung der Einkaufsliste.

Owner 2026-11-01: "schonmal schaetzung, was es kosten wird, finanzen kann damit
planen". Die Einkaufsliste rechnet Menge mal Preis je Einheit; der Preis kommt
von hier, weil nur das Lager weiss, was zuletzt bezahlt wurde.

Grundlage ist der freiwillige Einzelpreis am Posten (Stufe 4: ``preis`` fuer
die ganze ``eingangsmenge``). Ein Gesamtbetrag am Einkauf wird bei Vorraeten
bewusst nicht verteilt (RICHTUNG.md, "Laeufe"), er taucht hier also nicht auf.
Ein Produkt ohne einen einzigen Posten mit Preis fehlt in der Antwort, statt
mit einem geratenen Wert zu erscheinen.

Preisvergleich Stufe 1 (Owner 2026-11-07): ``je_kette`` nennt zusaetzlich den
letzten Preis je Ladenkette, aus Posten, deren Einkauf eine Kette traegt. Die
Einkaufsliste nimmt daraus den Tiefstpreis und zeigt das Logo. Ein Posten ohne
Einkauf oder mit Freitext-Laden zaehlt nur fuer den letzten Preis oben.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Einkauf, StockEntry

router = APIRouter(tags=["preise"])


class KettenPreisOut(BaseModel):
    kette: str
    unit: str
    preis_je_einheit: float
    letzter_preis: float
    letzte_menge: float
    am: date


class PreisOut(BaseModel):
    product_id: int
    unit: str
    preis_je_einheit: float
    letzter_preis: float
    letzte_menge: float
    je_kette: list[KettenPreisOut] = []


@router.get("/api/preise", response_model=list[PreisOut])
def preise(db: Session = Depends(get_db)):
    posten = db.execute(
        select(StockEntry, Einkauf)
        .outerjoin(Einkauf, StockEntry.einkauf_id == Einkauf.id)
        .where(StockEntry.preis.is_not(None), StockEntry.preis > 0,
               StockEntry.eingangsmenge.is_not(None), StockEntry.eingangsmenge > 0)
        .order_by(StockEntry.created_at.desc(), StockEntry.id.desc())
    ).all()
    ergebnis: dict[int, PreisOut] = {}
    kette_gesehen: set[tuple[int, str]] = set()
    for p, einkauf in posten:
        je_einheit = round(p.preis / p.eingangsmenge, 6)
        if p.product_id not in ergebnis:
            ergebnis[p.product_id] = PreisOut(
                product_id=p.product_id, unit=p.unit, preis_je_einheit=je_einheit,
                letzter_preis=round(p.preis, 2), letzte_menge=p.eingangsmenge,
            )
        if einkauf is None or not einkauf.kette or (p.product_id, einkauf.kette) in kette_gesehen:
            continue
        kette_gesehen.add((p.product_id, einkauf.kette))
        ergebnis[p.product_id].je_kette.append(KettenPreisOut(
            kette=einkauf.kette, unit=p.unit, preis_je_einheit=je_einheit,
            letzter_preis=round(p.preis, 2), letzte_menge=p.eingangsmenge, am=einkauf.am,
        ))
    return list(ergebnis.values())
