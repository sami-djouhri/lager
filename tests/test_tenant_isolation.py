"""Tests fuer das Tenant-Scoping (app/tenant.py): Basis-Isolation.

GELTUNGSBEREICH (ehrlich): Diese Tests sichern ab, dass das ORM-Tenant-Scoping
ueberhaupt aktiv ist und fremde subs 0 Zeilen sehen, sie fangen, wenn das
Scoping entfernt/gebrochen wird. Sie reproduzieren NICHT die spezifische
Cache-Poisoning-Variante des 2026-07-06-Bugs (nicht-Lambda-with_loader_criteria
backt den ersten sub in den Statement-Cache): diese entsteht nur im langlebigen
Prozess mit warmem Cache; ein frischer in-memory-Test faengt sie nicht (verifiziert:
laeuft auch mit non-Lambda gruen). Die Poisoning-Fix ist stattdessen live
verifiziert (fremder sub 24->0 nach Deploy). Der Lambda-Fix bleibt im Code.

Nutzt die ECHTE app.tenant._apply_tenant_scope-Funktion auf einer eigenen
in-memory-Session (die conftest ueberschreibt get_db, daher separate Fixture).
"""

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.tenant as tenant
from app.db import Base
from app.models import Product


def _make_sessionmaker():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    Sess = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    # echte Tenant-Scoping-Listener anhaengen (wie app.main es an SessionLocal tut)
    event.listen(Sess, "do_orm_execute", tenant._apply_tenant_scope)
    event.listen(Sess, "before_flush", tenant._stamp_tenant)
    return Sess


def _count(Sess, sub):
    s = Sess()
    s.info["owner_sub"] = sub
    try:
        return s.scalar(select(func.count()).select_from(Product))
    finally:
        s.close()


def test_tenant_isolation_foreign_sub_sees_nothing():
    """Basis-Isolation: fremder sub sieht keine fremden Daten (Scoping aktiv)."""
    Sess = _make_sessionmaker()

    # 2 Produkte fuer ownerA anlegen (owner_sub via before_flush gestempelt)
    seed = Sess()
    seed.info["owner_sub"] = "ownerA"
    seed.add(Product(name="Reis"))
    seed.add(Product(name="Nudeln"))
    seed.commit()
    seed.close()

    assert _count(Sess, "ownerA") == 2
    assert _count(Sess, "FOREIGN-XYZ") == 0
    assert _count(Sess, "ownerA") == 2
    assert _count(Sess, "FOREIGN-XYZ") == 0


def test_before_flush_stamps_owner_sub():
    Sess = _make_sessionmaker()
    s = Sess()
    s.info["owner_sub"] = "ownerB"
    p = Product(name="Milch")
    s.add(p)
    s.commit()
    assert p.owner_sub == "ownerB"
    s.close()
