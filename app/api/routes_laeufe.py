"""Einbuchen- und Lagern-Lauf, Einkauf, Fotos an Sachen (Stufe 4).

Die Regeln stehen in `app/services/laeufe.py`; hier wird nur geformt.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes_electronics import _asset_out
from app.api.routes_plaetze import _platz_out, _posten_ding, _sache_ding
from app.api.routes_stock import _entry_out
from app.db import get_db
from app.domain import DomainError
from app.events import INVENTORY_RESTOCKED, emit
from app.models import Einkauf, Sache
from app.schemas import (
    AbschlussIn,
    EinbuchenIn,
    EinbuchenOut,
    EinkaufOut,
    ElectronicAssetOut,
    LagernIn,
    LagernOut,
    TitelTrefferOut,
    VorschlagOut,
    ZuruecknehmenIn,
    ZuruecknehmenOut,
)
from app.services import fotos, medien
from app.services.barcode import BarcodeService
from app.services.laeufe import LaufService
from app.services.plaetze import PlatzService, ortstext, protokolliere
from app.services.sachen import isbn13, ist_strichcode

router = APIRouter(tags=["laeufe"])


@router.post("/api/laeufe/einbuchen", response_model=EinbuchenOut)
async def einbuchen(body: EinbuchenIn, db: Session = Depends(get_db)):
    erg = LaufService(db).einbuchen(body)
    db.commit()
    art = erg["art"]
    aus = EinbuchenOut(art=art, code=erg.get("code"),
                       produkt_neu=erg.get("produkt_neu", False),
                       anderer_bereich=erg.get("anderer_bereich"),
                       hinweis=erg.get("hinweis"))
    if erg.get("posten") is not None:
        posten = erg["posten"]
        db.refresh(posten)
        aus.posten = _entry_out(posten)
        emit(
            event_type=INVENTORY_RESTOCKED,
            external_id=f"stock-entry:{posten.id}",
            summary=f"{posten.quantity} {posten.unit} {aus.posten.product_name} eingebucht",
            entity_ref=f"product:{posten.product_id}",
            payload={"stock_entry_id": posten.id, "product_id": posten.product_id,
                     "quantity": posten.quantity, "unit": posten.unit,
                     "mhd": posten.mhd.isoformat() if posten.mhd else None,
                     "location": ortstext(posten.platz)},
        )
    if erg.get("sache") is not None:
        db.refresh(erg["sache"])
        aus.sache = _asset_out(erg["sache"])
    aus.vorhanden = [_asset_out(s) for s in erg.get("vorhanden", [])]
    aus.titel_offen = bool(erg.get("titel_offen"))
    if erg.get("sache") is not None and erg["sache"].bereich == medien.BEREICH \
            and art == "neu":
        medien.anstossen()
    if art == "menge_fehlt":
        p = erg["produkt"]
        aus.produkt_id, aus.produkt_name, aus.produkt_einheit = p.id, p.name, p.default_unit
    # Nur fuer Vorraete und nur fuer einen echten Strichcode: OpenFoodFacts
    # kennt Lebensmittel und Drogerie, keine Seriennummern. Ein Ausfall dort
    # ist kein Fehler des Laufs, dann fehlt nur der Vorschlag.
    # Nie fuer eine ISBN: die hat medien schon bei DNB und Open Library gesucht,
    # UPCitemdb kennt Buecher nicht, und jede Abfrage nach draussen nennt einen Titel.
    if art == "name_fehlt" and aus.code and ist_strichcode(aus.code) and not isbn13(aus.code):
        from app.bereiche import NACH_SCHLUESSEL, VORRAT
        if NACH_SCHLUESSEL[body.bereich].bauart == VORRAT:
            treffer = await BarcodeService().lookup(aus.code)
            if treffer:
                aus.vorschlag = VorschlagOut(name=treffer["name"], category=treffer.get("category"),
                                             quelle="OpenFoodFacts")
        elif body.bereich == medien.BEREICH:
            # Filme: der Titel von der Disc aus einer freien EAN-Datenbank, als
            # Vorschlag fuer die Titelsuche (Owner-Ausnahme 2026-11-06).
            treffer = await BarcodeService().lookup_film(aus.code)
            if treffer:
                aus.vorschlag = VorschlagOut(name=treffer["name"], category=None, quelle="UPCitemdb")
    return aus


@router.post("/api/laeufe/abschluss", response_model=EinkaufOut | None)
def abschluss(body: AbschlussIn, db: Session = Depends(get_db)):
    einkauf, zahlen = LaufService(db).abschliessen(body)
    db.commit()
    if body.bereich == medien.BEREICH and einkauf is not None:
        medien.anstossen()  # der Einstand gehoert in den Spiegel
    if einkauf is None:
        return None
    return EinkaufOut(id=einkauf.id, bereich=einkauf.bereich, am=einkauf.am,
                      laden=einkauf.laden, kette=einkauf.kette, gesamt=einkauf.gesamt,
                      **zahlen)


@router.get("/api/einkaeufe", response_model=list[EinkaufOut])
def einkaeufe(bereich: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    stmt = select(Einkauf).order_by(Einkauf.am.desc(), Einkauf.id.desc()).limit(min(limit, 500))
    if bereich:
        stmt = stmt.where(Einkauf.bereich == bereich)
    return [EinkaufOut(id=e.id, bereich=e.bereich, am=e.am, laden=e.laden, kette=e.kette,
                       gesamt=e.gesamt)
            for e in db.execute(stmt).scalars()]


@router.post("/api/laeufe/lagern", response_model=LagernOut)
def lagern(body: LagernIn, db: Session = Depends(get_db)):
    erg = LaufService(db).lagern(body)
    db.commit()
    aus = LagernOut(art=erg["art"], hinweis=erg.get("hinweis"),
                    vorher_pfad=erg.get("vorher_pfad", ""),
                    mhds=erg.get("mhds", []), zustaende=erg.get("zustaende", []),
                    gruende=erg.get("gruende", []), bereich=erg.get("bereich"),
                    vorher_platz_id=erg.get("vorher_platz_id"),
                    vorher_verbleib=erg.get("vorher_verbleib"),
                    vorher_grund=erg.get("vorher_grund"))
    if erg.get("platz") is not None:
        aus.platz = _platz_out(erg["platz"], PlatzService(db).belegung())
    if erg.get("posten") is not None:
        db.refresh(erg["posten"])
        aus.ding = _posten_ding(erg["posten"])
    if erg.get("sache") is not None:
        db.refresh(erg["sache"])
        aus.ding = _sache_ding(erg["sache"])
        if erg["sache"].bereich == medien.BEREICH:
            medien.anstossen()
    return aus


@router.post("/api/laeufe/einbuchen/zuruecknehmen", response_model=ZuruecknehmenOut)
def einbuchen_zuruecknehmen(body: ZuruecknehmenIn, db: Session = Depends(get_db)):
    text, foto, bereich = LaufService(db).einbuchen_zuruecknehmen(body)
    db.commit()
    # Erst nach dem Commit, der die Zeile nimmt (wie beim Loeschen einer Sache).
    fotos.loeschen(foto)
    if bereich == medien.BEREICH:
        medien.anstossen()
    return ZuruecknehmenOut(text=text)


@router.post("/api/laeufe/lagern/zuruecknehmen", response_model=ZuruecknehmenOut)
def lagern_zuruecknehmen(body: ZuruecknehmenIn, db: Session = Depends(get_db)):
    erg = LaufService(db).lagern_zuruecknehmen(body)
    db.commit()
    if erg.get("posten") is not None:
        db.refresh(erg["posten"])
        ding = _posten_ding(erg["posten"])
    else:
        db.refresh(erg["sache"])
        ding = _sache_ding(erg["sache"])
        if erg["sache"].bereich == medien.BEREICH:
            medien.anstossen()
    return ZuruecknehmenOut(text=f"{ding.name} zurückgenommen", ding=ding)


# ---------- Fotos an Sachen ----------

def _sache(db: Session, sache_id: int) -> Sache:
    # Ein Select und kein `db.get`: so laeuft die Abfrage sicher durch das
    # Mandanten-Scoping in `app/tenant.py`, auch wenn die Zeile schon in der
    # Sitzung laege.
    sache = db.execute(select(Sache).where(Sache.id == sache_id)).scalar_one_or_none()
    if sache is None:
        raise DomainError("Sache nicht gefunden", {"sache_id": sache_id})
    return sache


@router.post("/api/sachen/{sache_id}/foto", response_model=ElectronicAssetOut)
async def foto_hochladen(sache_id: int, request: Request, db: Session = Depends(get_db)):
    """Das Foto als rohes JPEG im Koerper (kein multipart, die Oberflaeche
    verkleinert ohnehin selbst und hat damit schon ein Blob)."""
    # Erst die angekuendigte Laenge, dann lesen: der Dienst hat 256 MB.
    angekuendigt = request.headers.get("content-length")
    if angekuendigt and angekuendigt.isdigit() and int(angekuendigt) > fotos.MAX_BYTES:
        raise DomainError(f"Bild zu groß ({int(angekuendigt) // 1024} KB, "
                          f"erlaubt {fotos.MAX_BYTES // 1024} KB)", {})
    rohdaten = await request.body()
    try:
        fotos.pruefen(rohdaten)
    except fotos.UngueltigesBild as fehler:
        raise DomainError(str(fehler), {}) from fehler
    sache = _sache(db, sache_id)
    alt = sache.foto
    name = fotos.speichern(sache.id, rohdaten, int(time.time() * 1000))
    sache.foto = name
    protokolliere(db, "sache", sache.id, "foto", alt, name)
    try:
        db.commit()
    except Exception:
        fotos.loeschen(name)
        raise
    # Das alte Bild erst nach dem Festschreiben wegwerfen.
    if alt and alt != name:
        fotos.loeschen(alt)
    if sache.bereich == medien.BEREICH:
        medien.anstossen()
    db.refresh(sache)
    return _asset_out(sache)


@router.get("/api/sachen/{sache_id}/foto")
def foto_zeigen(sache_id: int, db: Session = Depends(get_db)):
    sache = _sache(db, sache_id)
    pfad = fotos.datei(sache.foto)
    if not pfad:
        raise DomainError("Kein Foto", {"sache_id": sache_id})
    return FileResponse(pfad, media_type="image/jpeg", headers={
        "X-Content-Type-Options": "nosniff",
        # Der Name wechselt mit jedem Bild; `private`, weil ein Foto Besitz zeigt.
        "Cache-Control": "private, max-age=604800",
    })


@router.delete("/api/sachen/{sache_id}/foto", status_code=204)
def foto_entfernen(sache_id: int, db: Session = Depends(get_db)):
    sache = _sache(db, sache_id)
    alt = sache.foto
    if alt:
        protokolliere(db, "sache", sache.id, "foto", alt, None)
        sache.foto = None
        db.commit()
        fotos.loeschen(alt)
    return Response(status_code=204)


@router.get("/api/medien/titel", response_model=list[TitelTrefferOut])
def medien_titel(q: str, db: Session = Depends(get_db)):
    """Titelsuche im medien-Katalog fuer den Einbuch-Lauf (der Browser erreicht
    medien nicht mit dem Schluessel des Lagers, deshalb geht es hier durch)."""
    medien.pruefe_offen(db)
    return [TitelTrefferOut(**{k: t.get(k) for k in ("id", "titel", "medientyp", "jahr")})
            for t in medien.titel_suchen(q)]
