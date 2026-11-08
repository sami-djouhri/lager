"""Plaetze (Raumbaum, Etiketten, Kisten) und der Shopfloor.

Ein eigener Eingang neben den Bereichen (Owner 2026-11-01): ein Fach ist in
echt gemischt, deshalb zeigt ein Platz alles, was dort liegt, ueber alle
Bereiche hinweg.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.domain import DomainError
from app.models import SHOPFLOOR_GRUENDE, Platz, Sache, StockEntry
from app.schemas import (
    PlatzCreate,
    PlatzDingOut,
    PlatzInhaltOut,
    PlatzOut,
    PlatzUpdate,
    ShopfloorGruppeOut,
    ShopfloorOut,
    SucheOut,
)
from app.services.plaetze import PlatzService, falte, pfad

router = APIRouter(tags=["plaetze"])


def _platz_out(p: Platz, belegung: dict[int, dict[str, int]]) -> PlatzOut:
    b = belegung.get(p.id, {})
    return PlatzOut(
        id=p.id,
        kennung=p.kennung,
        name=p.name,
        art=p.art,
        eltern_id=p.eltern_id,
        pfad=pfad(p),
        inhalt=p.inhalt,
        bereich=p.bereich,
        kinder=b.get("kinder", 0),
        posten=b.get("posten", 0),
        sachen=b.get("sachen", 0),
    )


# Wie `frontend/src/einheiten.ts`: der Rohwert „piece" stand sonst als
# „2 piece" in der Platz- und der Lagern-Liste.
EINHEIT_NAMEN = {"piece": "Stk", "pieces": "Stk", "stk": "Stk"}


def _menge(e: StockEntry) -> str:
    menge = f"{e.quantity:g} {EINHEIT_NAMEN.get(e.unit, e.unit)}"
    return f"{menge} · bis {e.mhd.strftime('%d.%m.%Y')}" if e.mhd else menge


def _posten_ding(e: StockEntry) -> PlatzDingOut:
    return PlatzDingOut(
        art="posten",
        id=e.id,
        name=e.product.name if e.product else f"Produkt {e.product_id}",
        bereich=e.product.bereich if e.product else "",
        detail=_menge(e),
        platz_id=e.platz_id,
        platz_pfad=pfad(e.platz),
        mhd=e.mhd,
    )


def _sache_ding(s: Sache) -> PlatzDingOut:
    return PlatzDingOut(
        art="sache",
        id=s.id,
        name=s.name,
        bereich=s.bereich,
        detail=" · ".join(x for x in (s.brand, s.model) if x),
        platz_id=s.platz_id,
        platz_pfad=pfad(s.platz),
        shopfloor_grund=s.shopfloor_grund if s.verbleib == "shopfloor" else None,
        kennung=s.kennung,
        foto=s.foto,
        verbleib=s.verbleib,
    )


@router.get("/api/plaetze", response_model=list[PlatzOut])
def liste(art: str | None = None, bereich: str | None = None, db: Session = Depends(get_db)):
    svc = PlatzService(db)
    belegung = svc.belegung()
    plaetze = svc.alle()
    if art:
        plaetze = [p for p in plaetze if p.art == art]
    if bereich:
        plaetze = [p for p in plaetze if p.bereich == bereich]
    aus = [_platz_out(p, belegung) for p in plaetze]
    # Nach Pfad, damit ein Raum vor seinen Regalen steht.
    return sorted(aus, key=lambda p: p.pfad.lower())


@router.get("/api/plaetze/kennung/{kennung}", response_model=PlatzOut)
def per_kennung(kennung: str, db: Session = Depends(get_db)):
    svc = PlatzService(db)
    platz = svc.per_kennung(kennung)
    if platz is None:
        raise DomainError("Kein Platz mit dieser Kennung", {"kennung": kennung})
    return _platz_out(platz, svc.belegung())


@router.get("/api/plaetze/{platz_id}", response_model=PlatzInhaltOut)
def inhalt(platz_id: int, db: Session = Depends(get_db)):
    svc = PlatzService(db)
    platz = svc.get(platz_id)
    belegung = svc.belegung()
    unter = db.execute(select(Platz).where(Platz.eltern_id == platz.id)).scalars().all()
    posten = db.execute(
        select(StockEntry)
        .options(joinedload(StockEntry.product))
        .where(StockEntry.platz_id == platz.id, StockEntry.quantity > 0)
    ).scalars().all()
    sachen = db.execute(select(Sache).where(Sache.platz_id == platz.id, Sache.im_bestand())
                        ).scalars().all()
    dinge = [_posten_ding(e) for e in posten] + [_sache_ding(s) for s in sachen]
    return PlatzInhaltOut(
        platz=_platz_out(platz, belegung),
        unterplaetze=sorted((_platz_out(p, belegung) for p in unter), key=lambda p: p.name.lower()),
        dinge=sorted(dinge, key=lambda d: d.name.lower()),
    )


@router.post("/api/plaetze", response_model=PlatzOut, status_code=201)
def anlegen(body: PlatzCreate, db: Session = Depends(get_db)):
    svc = PlatzService(db)
    platz = svc.anlegen(
        name=body.name, art=body.art, eltern_id=body.eltern_id,
        inhalt=body.inhalt, bereich=body.bereich,
    )
    db.commit()
    db.refresh(platz)
    return _platz_out(platz, svc.belegung())


@router.put("/api/plaetze/{platz_id}", response_model=PlatzOut)
def aendern(platz_id: int, body: PlatzUpdate, db: Session = Depends(get_db)):
    svc = PlatzService(db)
    felder = {k: getattr(body, k) for k in body.model_fields_set}
    platz = svc.aendern(platz_id, felder)
    db.commit()
    db.refresh(platz)
    return _platz_out(platz, svc.belegung())


@router.delete("/api/plaetze/{platz_id}", status_code=204)
def loeschen(platz_id: int, db: Session = Depends(get_db)):
    PlatzService(db).loeschen(platz_id)
    db.commit()


@router.get("/api/shopfloor", response_model=ShopfloorOut)
def shopfloor(db: Session = Depends(get_db)):
    """Was eingebucht, aber nicht an seinem Platz ist (Vorbild medien).

    Feste Reihenfolge: zuerst „noch nicht eingelagert", denn das ist die
    Arbeit, die ansteht; danach die Gruende. Vorraete kennen keinen Grund
    (Owner: Vorrat nur Platz oder Shopfloor).
    """
    posten = db.execute(
        select(StockEntry)
        .options(joinedload(StockEntry.product))
        .where(StockEntry.platz_id.is_(None), StockEntry.quantity > 0)
    ).scalars().all()
    sachen = db.execute(select(Sache).where(Sache.verbleib == "shopfloor", Sache.im_bestand())
                        ).scalars().all()

    gruppen: list[ShopfloorGruppeOut] = []
    ohne = [_posten_ding(e) for e in posten]
    ohne += [_sache_ding(s) for s in sachen if s.shopfloor_grund is None]
    gruppen.append(ShopfloorGruppeOut(
        grund=None, name="Noch nicht eingelagert",
        dinge=sorted(ohne, key=lambda d: d.name.lower()),
    ))
    for schluessel, name in SHOPFLOOR_GRUENDE.items():
        dinge = [_sache_ding(s) for s in sachen if s.shopfloor_grund == schluessel]
        gruppen.append(ShopfloorGruppeOut(
            grund=schluessel, name=name, dinge=sorted(dinge, key=lambda d: d.name.lower()),
        ))
    return ShopfloorOut(gruppen=gruppen, anzahl=sum(len(g.dinge) for g in gruppen))


SUCHE_DINGE = 60
SUCHE_PLAETZE = 20


@router.get("/api/suche", response_model=SucheOut)
def suche(q: str = Query(..., min_length=1, max_length=100), db: Session = Depends(get_db)):
    """„Wo ist …" ueber alles: Posten mit Bestand, Sachen (auch Filme), Plaetze.

    Gesucht wird gefaltet (Umlaute wie ae, Gross/Klein egal) in Name, Kennung,
    Strichcode, Marke/Modell und Kisteninhalt. In Python statt per SQL-LIKE:
    SQLite faltet nur ASCII, „Käse" faende „KÄSE" sonst nicht. Bei ein paar
    tausend Zeilen je Mandant ist das schneller als jede Anfrage ueber das Netz.

    Ordnung: genaue Kennung oder Strichcode zuerst, dann Namen, die mit dem
    Suchwort beginnen, dann der Rest nach Name.
    """
    nadel = falte(q)

    def rang(name: str, genau: list[str | None]) -> tuple[int, str] | None:
        if any(g and falte(g) == nadel for g in genau):
            return (0, name.lower())
        n = falte(name)
        if n.startswith(nadel):
            return (1, name.lower())
        if nadel in n:
            return (2, name.lower())
        return None

    treffer: list[tuple[tuple[int, str], PlatzDingOut]] = []
    posten = db.execute(
        select(StockEntry)
        .options(joinedload(StockEntry.product), joinedload(StockEntry.platz))
        .where(StockEntry.quantity > 0)
    ).scalars().all()
    for e in posten:
        if e.product is None:
            continue
        r = rang(e.product.name, [e.product.barcode])
        if r is not None:
            treffer.append((r, _posten_ding(e)))
    for s in db.execute(select(Sache).options(joinedload(Sache.platz))
                        .where(Sache.im_bestand())).scalars().all():
        r = rang(s.name, [s.kennung, s.barcode, s.serial])
        if r is None and any(x and nadel in falte(x) for x in (s.brand, s.model, s.titel_huelle)):
            r = (2, s.name.lower())
        if r is not None:
            treffer.append((r, _sache_ding(s)))
    treffer.sort(key=lambda t: t[0])

    svc = PlatzService(db)
    belegung = svc.belegung()
    plaetze: list[tuple[tuple[int, str], Platz]] = []
    for p in svc.alle():
        r = rang(p.name, [p.kennung])
        if r is None and p.inhalt and nadel in falte(p.inhalt):
            r = (2, p.name.lower())
        if r is not None:
            plaetze.append((r, p))
    plaetze.sort(key=lambda t: t[0])

    return SucheOut(
        q=q,
        dinge=[d for _, d in treffer[:SUCHE_DINGE]],
        plaetze=[_platz_out(p, belegung) for _, p in plaetze[:SUCHE_PLAETZE]],
        mehr=len(treffer) > SUCHE_DINGE or len(plaetze) > SUCHE_PLAETZE,
    )
