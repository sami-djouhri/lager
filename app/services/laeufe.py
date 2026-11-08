"""Einbuchen- und Lagern-Lauf (Stufe 4, Vorbild medien).

Zwei Laeufe, wie in medien (Owner 2026-10-28 dort, 2026-11-01 hier):
**Einbuchen** bringt ein Ding ins Haus, **Lagern** bringt es ins Fach. Was
eingebucht ist, zaehlt als vorhanden, auch ohne Platz. Anders als in medien
darf der Einbuch-Lauf einen Platz als **Vorgabe** je Durchgang tragen (Owner:
der Wocheneinkauf soll ein Lauf sein, nicht zwei).

Der Lauf lebt im Browser. Hier gibt es keine Lauf-Tabelle: jeder Schritt ist
ein Aufruf, die Vorgabe kommt bei jedem Schritt mit, und erst der Abschluss
fasst die angelegten Dinge zu einem Einkauf zusammen. Ein abgebrochener Lauf
hinterlaesst damit gebuchte Dinge ohne Einkauf, nie einen halben Lauf.

Entscheide 2026-11-01, festgehalten in RICHTUNG.md:

* Vorrat: das MHD kommt als Vorschlag (uebliche Haltbarkeit des Produkts) und
  wird in der Quittung korrigiert. **Ein Posten je MHD**: ein zweiter Scan
  desselben Produkts im selben Lauf erhoeht die Menge, solange MHD und Platz
  gleich sind.
* Preis: Vorrat **Gesamt plus Einzelpreis**, nichts wird verteilt. Sachen:
  der Gesamtbetrag geht auf die Stuecke ohne eigenen Preis.
* Lagern: drei Richtungen. `ein` nimmt nur Offenes, `um` nur Eingelagertes,
  `aus` holt aus dem Fach (auch Vorraete). Ein Scan nimmt den ganzen Posten.
  Unterscheiden sich mehrere Posten im MHD, fragt der Lauf nach dem MHD; bei
  Sachen entscheidet der Zustand (medien: „Wenn Zustand identisch, ists ja
  sowieso egal").
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bereiche import EXEMPLAR, NACH_SCHLUESSEL, STUECK, VORRAT, gruende_fuer
from app.domain import DomainError, normalise_amount
from app.ketten import KETTEN, kette_aus_name
from app.models import (
    ABGAENGE,
    SHOPFLOOR_GRUENDE,
    ZUSTAENDE,
    ConsumptionEvent,
    Einkauf,
    Platz,
    Product,
    Sache,
    StockEntry,
)
from app.schemas import AbschlussIn, EinbuchenIn, LagernIn, ZuruecknehmenIn
from app.services import medien
from app.services.electronics import ElectronicAssetService
from app.services.plaetze import PlatzService, pfad, protokolliere
from app.services.sachen import (
    isbn13,
    ist_strichcode,
    naechste_kennung,
    per_kennung,
    platzkennung,
    sachkennung,
)

RICHTUNGEN = ("ein", "um", "aus")


def teil_aus_titel(text: str | None) -> str | None:
    """„Two and a Half Men – Staffel 3" -> „Staffel 3" (wie medien `teil_aus_huelle`).

    Eine Box ist EIN Stueck mit `teil` = „Staffel 1–5".
    """
    m = re.search(r"(?:staffel|season)\s*(\d+)(?:\s*[-–]\s*(\d+))?", text or "", re.I)
    if not m:
        return None
    return f"Staffel {m.group(1)}" + (f"–{m.group(2)}" if m.group(2) else "")


# Medientyp zum Medium, wenn der Lauf keinen nennt; Scheiben ohne Eintrag
# (DVD, Blu-ray, Box) entscheidet medien am Titel (Film oder Serie).
MEDIENTYP_ZUM_MEDIUM = {"Buch": "Buch", "CD": "Musik", "Vinyl": "Musik",
                        "Spiel-Disc": "Spiel", "Spiel-Modul": "Spiel"}


def standard_zustand(bauart: str) -> str:
    # Filme wie in medien: was nicht angesehen wurde, ist „Ungeprueft"; dann
    # entscheidet die Dubletten-Regel dort bewusst nichts.
    return "Ungeprüft" if bauart == EXEMPLAR else "Gut"


class Ergebnis(dict):
    """Antwort eines Schritts; die Route formt daraus das Schema."""


def _bereich(schluessel: str, bauarten: tuple[str, ...]):
    b = NACH_SCHLUESSEL.get(schluessel)
    if b is None:
        raise DomainError(f"Unbekannter Bereich '{schluessel}'", {})
    if b.bauart not in bauarten:
        raise DomainError(f"Im Bereich „{b.name}“ gibt es (noch) keinen Einbuch-Lauf",
                          {"bauart": b.bauart})
    return b


def _kein_etikett(code: str) -> None:
    # Ohne diese Pruefung entstuende ein Produkt oder eine Sache namens „L-001".
    if platzkennung(code):
        raise DomainError("Das ist ein Platz-Etikett. Plätze scannt man im Lagern-Lauf.", {})


def _falte(text: str) -> str:
    return " ".join((text or "").lower().split())


class LaufService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Einbuchen
    # ------------------------------------------------------------------

    def einbuchen(self, body: EinbuchenIn) -> Ergebnis:
        b = _bereich(body.bereich, (VORRAT, STUECK, EXEMPLAR))
        if b.bauart == EXEMPLAR:
            medien.pruefe_offen(self.db)
        platz = PlatzService(self.db).get(body.platz_id) if body.platz_id is not None else None
        code = (body.code or "").strip()
        if code:
            _kein_etikett(code)
        if b.bauart == VORRAT:
            return self._vorrat_einbuchen(body, b.schluessel, code, platz)
        return self._sache_einbuchen(body, b.schluessel, b.bauart, code, platz)

    def _vorrat_einbuchen(self, body: EinbuchenIn, bereich: str, code: str,
                          platz: Platz | None) -> Ergebnis:
        if code and sachkennung(code):
            raise DomainError("Das ist ein Stück-Etikett. Sachen bucht man unter Technik & Sachen ein.", {})
        produkt = None
        if code:
            produkt = self.db.execute(
                select(Product).where(Product.barcode == code)
            ).scalar_one_or_none()
        name = (body.name or "").strip()
        produkt_neu = False
        if produkt is None and name:
            produkt = self._produkt_per_name(name, bereich)
            if produkt is None:
                produkt = Product(name=name, bereich=bereich, default_unit="piece",
                                  barcode=code or None, category=body.kategorie or None)
                self.db.add(produkt)
                self.db.flush()
                produkt_neu = True
            elif code and not produkt.barcode:
                # Das Produkt gab es schon ohne Strichcode; ab jetzt findet ihn der Scan.
                produkt.barcode = code
        if produkt is None:
            return Ergebnis(art="name_fehlt", code=code or None)

        menge = self._menge(produkt, body)
        if menge is None:
            return Ergebnis(art="menge_fehlt", code=code or None, produkt=produkt)
        quantity, unit = menge

        mhd = body.mhd
        if mhd is None and produkt.shelf_life_days_default:
            mhd = date.today() + timedelta(days=produkt.shelf_life_days_default)
        platz_id = platz.id if platz else None

        # Ein Posten je MHD (Owner): derselbe Scan noch einmal im selben Lauf
        # erhoeht die Menge, statt eine zweite Zeile anzulegen.
        if body.lauf_posten:
            frueher = self.db.execute(
                select(StockEntry).where(
                    StockEntry.id.in_(body.lauf_posten),
                    StockEntry.product_id == produkt.id,
                    StockEntry.unit == unit,
                    StockEntry.mhd.is_(None) if mhd is None else StockEntry.mhd == mhd,
                    StockEntry.platz_id.is_(None) if platz_id is None
                    else StockEntry.platz_id == platz_id,
                    StockEntry.quantity > 0,
                ).order_by(StockEntry.id)
            ).scalars().first()
            if frueher is not None:
                protokolliere(self.db, "posten", frueher.id, "quantity",
                              frueher.quantity, frueher.quantity + quantity)
                frueher.quantity += quantity
                frueher.eingangsmenge = (frueher.eingangsmenge or 0) + quantity
                if body.preis is not None:
                    frueher.preis = round((frueher.preis or 0) + body.preis, 2)
                self.db.flush()
                return Ergebnis(art="mehr", posten=frueher, produkt=produkt,
                                anderer_bereich=self._anders(produkt, bereich))

        posten = StockEntry(product_id=produkt.id, quantity=quantity, unit=unit, mhd=mhd,
                            purchase_date=date.today(), platz_id=platz_id,
                            preis=body.preis, eingangsmenge=quantity)
        self.db.add(posten)
        self.db.flush()
        return Ergebnis(art="neu", posten=posten, produkt=produkt, produkt_neu=produkt_neu,
                        anderer_bereich=self._anders(produkt, bereich))

    @staticmethod
    def _anders(produkt: Product, bereich: str) -> str | None:
        return produkt.bereich if produkt.bereich != bereich else None

    def _produkt_per_name(self, name: str, bereich: str) -> Product | None:
        gesucht = _falte(name)
        kandidaten = self.db.execute(
            select(Product).where(func.lower(Product.name) == name.lower())
        ).scalars().all() or [
            p for p in self.db.execute(select(Product).where(Product.bereich == bereich)).scalars()
            if _falte(p.name) == gesucht
        ]
        # Im eigenen Bereich zuerst, dann irgendwo (Name ist je Mandant eindeutig).
        return next((p for p in kandidaten if p.bereich == bereich), kandidaten[0] if kandidaten else None)

    def _menge(self, produkt: Product, body: EinbuchenIn) -> tuple[float, str] | None:
        """Menge und Einheit eines Scans.

        Reihenfolge: ausdruecklich mitgegeben, uebliche Packungsgroesse, die
        Menge des letzten Postens dieses Produkts, ein Stueck bei Stueckware.
        Ein Produkt in Gramm ohne jeden Anhaltspunkt bekommt **keine**
        erfundene Menge, sondern die Rueckfrage `menge_fehlt`: „1 g Mehl" saehe
        aus wie eine Buchung und waere keine.
        """
        if body.menge is not None:
            return normalise_amount(body.menge, body.einheit or produkt.default_unit)
        if produkt.typical_pack_sizes:
            return float(produkt.typical_pack_sizes[0]), produkt.default_unit
        letzter = self.db.execute(
            select(StockEntry).where(StockEntry.product_id == produkt.id)
            .order_by(StockEntry.id.desc())
        ).scalars().first()
        if letzter is not None:
            return float(letzter.eingangsmenge or letzter.quantity or 1), letzter.unit
        if produkt.default_unit == "piece":
            return 1.0, "piece"
        return None

    def _sache_einbuchen(self, body: EinbuchenIn, bereich: str, bauart: str, code: str,
                         platz: Platz | None) -> Ergebnis:
        exemplar = bauart == EXEMPLAR
        # Bücher: eine ISBN gilt als Strichcode, auch eingetippt als ISBN-10 mit
        # Bindestrichen; sonst würde „3-499-22660-X" eine Seriennummer.
        isbn = isbn13(code) if exemplar and code else None
        if isbn:
            code = isbn
        if code and sachkennung(code):
            # Das eigene Etikett ist eindeutig dasselbe Stueck: daraus darf nie
            # ein Zugang werden, sonst legt ein Scan des Etiketts eine Dublette an.
            s = per_kennung(self.db, code)
            if s is None:
                raise DomainError(f"Kein Stück mit der Kennung {sachkennung(code)}", {})
            _nicht_abgegangen(s)
            return Ergebnis(art="wiedergesehen", sache=s)
        strich = bool(code) and ist_strichcode(code)
        if code and not strich:
            s = self.db.execute(select(Sache).where(Sache.serial == code)).scalar_one_or_none()
            if s is not None:
                _nicht_abgegangen(s)
                return Ergebnis(art="wiedergesehen", sache=s)

        name = (body.name or "").strip()
        # Nur im eigenen Bereich: sonst meldete ein DVD-Strichcode im
        # Technik-Lauf „davon gibt es schon ein Stueck".
        im_bereich = (select(Sache).where(Sache.bereich == bereich, Sache.im_bestand())
                      .order_by(Sache.id))
        treffer: list[Sache] = []
        if strich:
            treffer = list(self.db.execute(im_bereich.where(Sache.barcode == code)).scalars())
        if not treffer and exemplar and body.titel_id is not None:
            treffer = list(self.db.execute(im_bereich.where(Sache.titel_id == body.titel_id)).scalars())
        elif not treffer and name and not exemplar:
            treffer = list(self.db.execute(
                im_bereich.where(func.lower(Sache.name) == name.lower())).scalars())
        # Beim Auspacken eines Konvoluts ist das Stueck in der Hand immer ein
        # neues (medien). `bekannt` zeigt nur, was schon da ist, und ein Griff
        # bestaetigt; gefragt „dasselbe oder ein zweites?" wird nicht.
        if treffer and not body.bestaetigt:
            return Ergebnis(art="bekannt", vorhanden=treffer, code=code or None)
        vorlage = treffer[0] if treffer else None
        if not name and vorlage is not None:
            name = vorlage.name

        titel_id = teil = None
        titel_offen = False
        medium = body.medium or (vorlage.medium if vorlage is not None else None)
        if exemplar and not medium:
            # Ohne Vorgabe (Lager-App bis 0.8): eine ISBN ist ein Buch, sonst die Scheibe.
            medium = "Buch" if isbn else "DVD"
        medientyp = body.medientyp or (MEDIENTYP_ZUM_MEDIUM.get(medium) if exemplar else None)
        if exemplar and isbn and not name and body.titel_id is None:
            # Ein Buch braucht nur den Scan: medien kennt die ISBN oder schlägt
            # sie nach (je Buch einzeln, medien RICHTUNG Stufe 6).
            try:
                t = medien.titel_holen("", medientyp or "Buch", isbn)
                titel_id, name = int(t["id"]), t["titel"]
                medientyp = medientyp or t.get("medientyp")
            except medien.IsbnUnbekannt:
                return Ergebnis(art="name_fehlt", code=code,
                                hinweis="Die ISBN kennt keine Quelle. Titel bitte eintippen.")
            except medien.NichtErreichbar:
                return Ergebnis(art="name_fehlt", code=code,
                                hinweis="medien antwortet nicht, die ISBN lässt sich gerade nicht "
                                        "nachschlagen. Mit dem Titel geht es trotzdem.")
        if not name:
            return Ergebnis(art="name_fehlt", code=code or None)

        if exemplar and titel_id is None:
            # Der Titel kommt live aus medien und wird dort bei Bedarf angelegt
            # (Owner). `name` traegt danach den kanonischen Katalogtitel.
            if body.titel_id is not None:
                titel_id = body.titel_id
                name = (body.katalogtitel or "").strip() or name
            elif vorlage is not None and vorlage.titel_id is not None and not body.name:
                titel_id, name = vorlage.titel_id, vorlage.name
            else:
                try:
                    t = medien.titel_holen(name, medientyp, isbn)
                    titel_id, name = int(t["id"]), t["titel"]
                    medientyp = medientyp or t.get("medientyp")
                except medien.NichtErreichbar:
                    # Der Lauf geht weiter: das Stueck entsteht mit dem Namen
                    # von der Huelle, den Titel traegt der Spiegel-Laeufer nach,
                    # sobald medien wieder antwortet (`medien.titel_nachtragen`).
                    titel_offen = True
        if exemplar:
            teil = (body.teil or "").strip() or teil_aus_titel(body.name) or \
                (vorlage.teil if vorlage is not None else None)

        zustand = body.zustand if body.zustand in ZUSTAENDE else standard_zustand(bauart)
        sache = Sache(
            kennung=naechste_kennung(self.db),
            bereich=bereich,
            name=name,
            category=vorlage.category if vorlage else body.kategorie,
            brand=vorlage.brand if vorlage else None,
            model=vorlage.model if vorlage else None,
            barcode=code if strich else None,
            serial=code if code and not strich else None,
            condition=zustand,
            status="aktiv",
            sell_decision="behalten",
            manual_pin=0,
            purchase_date=date.today(),
            purchase_price=body.preis,
            platz_id=platz.id if platz else None,
            titel_id=titel_id,
            teil=teil,
            edition=(body.edition or "").strip() or None,
            medium=medium,
            medientyp=medientyp,
            titel_huelle=(body.name or None) if exemplar else None,
        )
        svc = ElectronicAssetService(self.db)
        # Eingebucht vor eingelagert: mit Platz liegt sie dort, sonst ohne Grund
        # auf dem Shopfloor (ein Zugang bekommt nie von selbst einen Grund).
        svc._setze_verbleib(sache, "eingelagert" if platz else "shopfloor", None)
        svc._apply_decision(sache)
        self.db.add(sache)
        self.db.flush()
        protokolliere(self.db, "sache", sache.id, "angelegt", None, sache.kennung)
        return Ergebnis(art="neu", sache=sache, titel_offen=titel_offen)

    # ------------------------------------------------------------------
    # Abschluss: der Einkauf
    # ------------------------------------------------------------------

    def abschliessen(self, body: AbschlussIn) -> tuple[Einkauf | None, dict]:
        b = _bereich(body.bereich, (VORRAT, STUECK, EXEMPLAR))
        posten = list(self.db.execute(
            select(StockEntry).where(StockEntry.id.in_(body.posten))
        ).scalars()) if body.posten else []
        sachen = list(self.db.execute(
            select(Sache).where(Sache.id.in_(body.sachen))
        ).scalars()) if body.sachen else []
        laden = (body.laden or "").strip() or None
        if body.kette is not None and body.kette not in KETTEN:
            raise DomainError("Unbekannte Ladenkette", {"kette": body.kette})
        kette = body.kette or kette_aus_name(laden)
        if kette and not laden:
            laden = KETTEN[kette]
        if body.gesamt is None and laden is None:
            # Nichts zu einem Einkauf zu sagen: die Dinge sind ja schon gebucht.
            return None, {}
        if not posten and not sachen:
            raise DomainError("Dieser Lauf hat nichts eingebucht", {})
        schon = [x for x in (*posten, *sachen) if x.einkauf_id is not None]
        if schon:
            raise DomainError("Ein Teil davon gehört schon zu einem Einkauf",
                              {"anzahl": len(schon)})

        am = body.am or date.today()
        einkauf = Einkauf(bereich=b.schluessel, am=am, laden=laden, kette=kette,
                          gesamt=body.gesamt)
        self.db.add(einkauf)
        self.db.flush()
        for p in posten:
            p.einkauf_id = einkauf.id
            p.purchase_date = am
        for s in sachen:
            s.einkauf_id = einkauf.id
            s.purchase_date = am
            if laden and not s.purchase_source:
                s.purchase_source = laden

        verteilt: dict[int, float] = {}
        einzeln = sum(p.preis or 0 for p in posten) + sum(s.purchase_price or 0 for s in sachen)
        ohne = [s for s in sachen if s.purchase_price is None]
        if body.gesamt is not None and ohne:
            rest = round(body.gesamt - einzeln, 2)
            if rest < 0:
                raise DomainError(
                    f"Die Einzelpreise ergeben schon {einzeln:.2f} €, mehr als der Gesamtbetrag",
                    {"einzelpreise": round(einzeln, 2), "gesamt": body.gesamt},
                )
            verteilt = verteilen(ohne, rest)
            svc = ElectronicAssetService(self.db)
            for s in ohne:
                protokolliere(self.db, "sache", s.id, "purchase_price", None, verteilt[s.id])
                s.purchase_price = verteilt[s.id]
                svc._apply_decision(s)
        self.db.flush()
        ohne_preis = sum(1 for p in posten if p.preis is None) + \
            sum(1 for s in sachen if s.purchase_price is None)
        return einkauf, {
            "posten": len(posten), "sachen": len(sachen),
            "einzelpreise": round(einzeln, 2), "ohne_preis": ohne_preis, "verteilt": verteilt,
        }

    # ------------------------------------------------------------------
    # Lagern
    # ------------------------------------------------------------------

    def lagern(self, body: LagernIn) -> Ergebnis:
        if body.richtung not in RICHTUNGEN:
            raise DomainError("Richtung muss „ein“, „um“ oder „aus“ sein", {})
        code = body.code.strip()
        # Eine eingetippte ISBN-10 meint das Buch, das unter der ISBN-13 eingebucht ist.
        code = isbn13(code) or code
        psvc = PlatzService(self.db)
        if platzkennung(code):
            platz = psvc.per_kennung(code)
            if platz is None:
                raise DomainError(f"Kein Platz mit der Kennung {platzkennung(code)}", {})
            return Ergebnis(art="platz", platz=platz)

        ziel = None
        if body.richtung in ("ein", "um"):
            if body.platz_id is None:
                raise DomainError("Zuerst das Fach-Etikett scannen", {})
            ziel = psvc.get(body.platz_id)
        elif body.grund is not None and body.grund not in SHOPFLOOR_GRUENDE:
            raise DomainError(f"Unbekannter Grund '{body.grund}'",
                              {"erlaubt": list(SHOPFLOOR_GRUENDE)})

        sachen = self._sachen_zum_code(code)
        if sachen:
            return self._sache_lagern(sachen, body, ziel)
        produkt = None
        if not sachkennung(code):
            produkt = self.db.execute(
                select(Product).where(Product.barcode == code)
            ).scalar_one_or_none()
        if produkt is None:
            return Ergebnis(art="unbekannt",
                            hinweis="Diesen Code kennt das Lager nicht. Erst einbuchen.")
        return self._posten_lagern(produkt, body, ziel)

    def _sachen_zum_code(self, code: str) -> list[Sache]:
        if sachkennung(code):
            s = per_kennung(self.db, code)
            if s:
                _nicht_abgegangen(s)
            return [s] if s else []
        if not ist_strichcode(code):
            s = self.db.execute(select(Sache).where(Sache.serial == code)).scalar_one_or_none()
            if s is not None:
                _nicht_abgegangen(s)
                return [s]
        return list(self.db.execute(
            select(Sache).where(Sache.barcode == code, Sache.im_bestand()).order_by(Sache.id)
        ).scalars())

    def _sache_lagern(self, alle: list[Sache], body: LagernIn, ziel: Platz | None) -> Ergebnis:
        if body.richtung == "ein":
            passend = [s for s in alle if s.verbleib != "eingelagert"]
        else:
            passend = [s for s in alle if s.verbleib == "eingelagert"]
            if body.richtung == "um":
                passend = [s for s in passend if s.platz_id != ziel.id]
        if not passend:
            return Ergebnis(art="passt_nicht", hinweis=_warum_nicht(body.richtung, alle, ziel))

        sache = passend[0]
        if len(passend) > 1:
            zustaende = sorted({s.condition or "Gut" for s in passend})
            if body.zustand:
                gleich = [s for s in passend if (s.condition or "Gut") == body.zustand]
                if gleich:
                    sache = gleich[0]
            elif len(zustaende) > 1:
                # Nur fragen, wenn es einen Unterschied gibt (medien).
                return Ergebnis(art="welches", zustaende=zustaende)

        vorher = pfad(sache.platz)
        stand = {"vorher_platz_id": sache.platz_id, "vorher_verbleib": sache.verbleib,
                 "vorher_grund": sache.shopfloor_grund}
        svc = ElectronicAssetService(self.db)
        if body.richtung == "aus":
            # Die Gruende gelten je Bereich (Owner): ein Film geht zum Rippen,
            # ein Akkuschrauber in Reparatur. Passt der Grund des Laufs nicht zum
            # Stueck, fragt der Lauf nach einem aus dessen Bereich.
            erlaubt = gruende_fuer(sache.bereich)
            if body.grund not in erlaubt:
                return Ergebnis(art="grund_fehlt", gruende=list(erlaubt), bereich=sache.bereich)
            svc._setze_verbleib(sache, "shopfloor", body.grund)
        else:
            protokolliere(self.db, "sache", sache.id, "platz_id", sache.platz_id, ziel.id)
            sache.platz_id = ziel.id
            sache.platz = ziel
            svc._setze_verbleib(sache, "eingelagert", None)
        svc._apply_decision(sache)
        self.db.flush()
        return Ergebnis(art="gebucht", sache=sache, vorher_pfad=vorher, **stand)

    def _posten_lagern(self, produkt: Product, body: LagernIn, ziel: Platz | None) -> Ergebnis:
        alle = list(self.db.execute(
            select(StockEntry).where(StockEntry.product_id == produkt.id, StockEntry.quantity > 0)
            .order_by(StockEntry.id)
        ).scalars())
        if body.richtung == "ein":
            passend = [p for p in alle if p.platz_id is None]
        else:
            passend = [p for p in alle if p.platz_id is not None]
            if body.richtung == "um":
                passend = [p for p in passend if p.platz_id != ziel.id]
        if not passend:
            return Ergebnis(art="passt_nicht",
                            hinweis=_warum_nicht_posten(body.richtung, produkt, alle, ziel))

        mhds = sorted({p.mhd for p in passend}, key=lambda m: (m is None, m or date.max))
        if len(mhds) > 1:
            if body.mhd is None and not body.ohne_mhd:
                return Ergebnis(art="welches", mhds=mhds)
            gewaehlt = None if body.ohne_mhd else body.mhd
            passend = [p for p in passend if p.mhd == gewaehlt]
            if not passend:
                raise DomainError("Kein Posten mit diesem MHD", {})
        posten = passend[0]
        vorher = pfad(posten.platz)
        vorher_platz_id = posten.platz_id
        neu = None if body.richtung == "aus" else ziel.id
        protokolliere(self.db, "posten", posten.id, "platz_id", posten.platz_id, neu)
        posten.platz_id = neu
        posten.platz = ziel if neu is not None else None
        self.db.flush()
        return Ergebnis(art="gebucht", posten=posten, vorher_pfad=vorher,
                        vorher_platz_id=vorher_platz_id)

    # ------------------------------------------------------------------
    # Zuruecknehmen: ein Fehlscan aus der Quittung
    # ------------------------------------------------------------------

    def einbuchen_zuruecknehmen(self, body: ZuruecknehmenIn) -> tuple[str, str | None, str | None]:
        """Ein im Lauf eingebuchtes Ding geht wieder. Liefert Text, ein Foto,
        das die Route erst NACH dem Commit loescht, und den Bereich einer Sache
        (geht ein Film, muss der Spiegel in medien nachziehen).

        Nur, solange die Zeile noch frisch ist: nichts verbraucht und keinem
        Einkauf zugeordnet. Danach ist es kein Fehlscan mehr, sondern Bestand
        mit Geschichte, und der geht ueber Ausbuchen bzw. Loeschen.
        Ein im Lauf angelegtes Produkt bleibt stehen: es ist ein Name, kein
        Bestand, und ein zweiter Scan desselben Codes faende es sonst nicht.
        """
        _genau_eins(body)
        if body.posten_id is not None:
            posten = self.db.execute(
                select(StockEntry).where(StockEntry.id == body.posten_id)
            ).scalar_one_or_none()
            if posten is None:
                raise DomainError("Posten nicht gefunden", {"posten_id": body.posten_id})
            if posten.einkauf_id is not None:
                raise DomainError("Der Posten gehört schon zu einem Einkauf", {})
            verbraucht = self.db.execute(
                select(func.count()).select_from(ConsumptionEvent)
                .where(ConsumptionEvent.stock_entry_id == posten.id)
            ).scalar_one()
            if verbraucht:
                raise DomainError("Davon ist schon etwas verbraucht. Die Menge in der Quittung ändern.", {})
            name = posten.product.name if posten.product else "Posten"
            protokolliere(self.db, "posten", posten.id, "geloescht", posten.quantity, None)
            self.db.delete(posten)
            self.db.flush()
            return f"{name} zurückgenommen", None, None

        sache = self.db.execute(select(Sache).where(Sache.id == body.sache_id)).scalar_one_or_none()
        if sache is None:
            raise DomainError("Sache nicht gefunden", {"sache_id": body.sache_id})
        if sache.einkauf_id is not None:
            raise DomainError("Das Stück gehört schon zu einem Einkauf", {})
        text, foto, bereich = f"{sache.kennung} {sache.name} zurückgenommen", sache.foto, sache.bereich
        # Die Kennung bleibt im Verlauf und wird nie neu vergeben (ein Etikett klebt).
        ElectronicAssetService(self.db).delete(sache.id)
        return text, foto, bereich

    def lagern_zuruecknehmen(self, body: ZuruecknehmenIn) -> Ergebnis:
        """Den Stand vor einer Lagern-Buchung wiederherstellen.

        Wiederhergestellt wird, was die Quittung mitbringt, nicht was im
        Verlauf steht: der Verlauf kennt Felder, nicht Buchungen, und zwei
        Scans desselben Dings waeren dort nicht auseinanderzuhalten.
        """
        _genau_eins(body)
        platz = (PlatzService(self.db).get(body.vorher_platz_id)
                 if body.vorher_platz_id is not None else None)
        if body.posten_id is not None:
            posten = self.db.execute(
                select(StockEntry).where(StockEntry.id == body.posten_id)
            ).scalar_one_or_none()
            if posten is None:
                raise DomainError("Posten nicht gefunden", {"posten_id": body.posten_id})
            protokolliere(self.db, "posten", posten.id, "platz_id", posten.platz_id,
                          platz.id if platz else None)
            posten.platz_id = platz.id if platz else None
            posten.platz = platz
            self.db.flush()
            return Ergebnis(posten=posten)

        sache = self.db.execute(select(Sache).where(Sache.id == body.sache_id)).scalar_one_or_none()
        if sache is None:
            raise DomainError("Sache nicht gefunden", {"sache_id": body.sache_id})
        if body.vorher_verbleib is None:
            raise DomainError("Für Sachen fehlt der Verbleib vor der Buchung", {})
        protokolliere(self.db, "sache", sache.id, "platz_id", sache.platz_id,
                      platz.id if platz else None)
        sache.platz_id = platz.id if platz else None
        sache.platz = platz
        svc = ElectronicAssetService(self.db)
        svc._setze_verbleib(sache, body.vorher_verbleib, body.vorher_grund)
        svc._apply_decision(sache)
        self.db.flush()
        return Ergebnis(sache=sache)


def _genau_eins(body: ZuruecknehmenIn) -> None:
    if (body.posten_id is None) == (body.sache_id is None):
        raise DomainError("Genau eins von posten_id und sache_id angeben", {})


def _nicht_abgegangen(s: Sache) -> None:
    """Ein Etikett klebt auch an einer verkauften Sache. Sie still wieder
    einzulagern hiesse, ein Stueck zu fuehren, das nicht mehr im Haus ist."""
    if s.abgang is not None:
        wie = ABGAENGE.get(s.abgang, s.abgang).lower()
        am = f" am {s.abgang_am.strftime('%d.%m.%Y')}" if s.abgang_am else ""
        raise DomainError(f"{s.kennung} ist {wie}{am}. War das ein Irrtum, den Abgang "
                          "auf der Seite des Bereichs zurücknehmen.", {"kennung": s.kennung})


def _warum_nicht(richtung: str, alle: list[Sache], ziel: Platz | None) -> str:
    s = alle[0]
    if richtung == "ein":
        return (f"{s.name} liegt schon in {pfad(s.platz)}. "
                "Zum Umziehen „Umlagern“ wählen.")
    if richtung == "um" and ziel is not None and any(x.platz_id == ziel.id for x in alle):
        return f"{s.name} liegt schon hier."
    return f"{s.name} ist nicht eingelagert. Zuerst „Einlagern“ wählen."


def _warum_nicht_posten(richtung: str, produkt: Product, alle: list[StockEntry],
                        ziel: Platz | None) -> str:
    if not alle:
        return f"Von {produkt.name} ist nichts auf Lager. Erst einbuchen."
    if richtung == "ein":
        return (f"{produkt.name} ist schon ganz eingelagert. "
                "Zum Umziehen „Umlagern“ wählen.")
    if richtung == "um" and ziel is not None and all(p.platz_id == ziel.id for p in alle
                                                    if p.platz_id is not None) \
            and any(p.platz_id is not None for p in alle):
        return f"{produkt.name} liegt schon hier."
    return f"{produkt.name} ist noch nicht eingelagert. Zuerst „Einlagern“ wählen."


def verteilen(sachen: list[Sache], betrag: float) -> dict[int, float]:
    """Einen Betrag auf Sachen verteilen, auf den Cent genau.

    Gewichtet nach Marktwert, wenn ihn **jede** Sache hat; sonst zu gleichen
    Teilen. Ein halb gewichteter Satz (drei mit Marktwert, zwei ohne) haette
    den zwei ohne einen Anteil von null gegeben, und das ist kein Preis.
    Der Rundungsrest landet beim groessten Posten, damit die Summe exakt stimmt
    (medien `konvolut_verteilen`).
    """
    if not sachen:
        return {}
    werte = [s.effective_market_value for s in sachen]
    if all(w is not None and w > 0 for w in werte):
        gewichte = [float(w) for w in werte]
    else:
        gewichte = [1.0] * len(sachen)
    summe = sum(gewichte)
    anteile = {s.id: round(betrag * g / summe, 2) for s, g in zip(sachen, gewichte)}
    rest = round(betrag - sum(anteile.values()), 2)
    if rest:
        groesster = max(zip(sachen, gewichte), key=lambda x: (x[1], -x[0].id))[0]
        anteile[groesster.id] = round(anteile[groesster.id] + rest, 2)
    return anteile
