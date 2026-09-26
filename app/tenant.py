"""Multi-Tenant-Scoping auf ORM-Ebene (fail-closed).

Statt jede einzelne Query zu editieren (eine vergessene = Cross-Tenant-Leck),
haengt sich das Scoping global in die Session:

* do_orm_execute: jede SELECT gegen ein Tenant-Modell bekommt automatisch
  ``owner_sub == <session-sub>`` angehaengt (with_loader_criteria, inkl. Joins).
* before_flush: neue Tenant-Objekte werden mit dem sub der Session gestempelt.

Der sub steht in ``session.info["owner_sub"]`` (gesetzt in get_db aus dem
X-Saganta-Sub-Header, Fallback DEFAULT_OWNER_SUB fuer interne Aufrufe).

Ausnahme: mit ``execution_options(skip_tenant=True)`` laesst sich eine Query
bewusst tenant-uebergreifend ausfuehren (aktuell nirgends noetig).
"""

from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from app.config import settings
from app.db import SessionLocal
from app.models import ConsumptionEvent, ElectronicAsset, Product, StockEntry

TENANT_MODELS = (Product, StockEntry, ConsumptionEvent, ElectronicAsset)


def _session_sub(session) -> str:
    return session.info.get("owner_sub") or settings.DEFAULT_OWNER_SUB


@event.listens_for(SessionLocal, "do_orm_execute")
def _apply_tenant_scope(execute_state) -> None:
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("skip_tenant"):
        return
    sub = _session_sub(execute_state.session)
    for model in TENANT_MODELS:
        # WICHTIG: Kriterium als Lambda. with_loader_criteria cached das SQL-Kriterium
        # stark; ein *nicht*-Lambda mit variablem Wert (model.owner_sub == sub) backt
        # den ERSTEN sub (beim Seed/Start = DEFAULT_OWNER_SUB) in den Statement-Cache
        # und wiederverwendet ihn fuer alle folgenden Requests → Tenant-Scoping filtert
        # effektiv immer auf den DEFAULT-Owner = Cross-Tenant-Datenleck. Die Lambda
        # laesst SQLAlchemy `sub` als variablen Closure-Bindparam behandeln (Doku-Pattern).
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                model,
                lambda cls: cls.owner_sub == sub,
                include_aliases=True,
            )
        )


@event.listens_for(SessionLocal, "before_flush")
def _stamp_tenant(session, _flush_context, _instances) -> None:
    sub = _session_sub(session)
    for obj in session.new:
        if isinstance(obj, TENANT_MODELS) and not getattr(obj, "owner_sub", None):
            obj.owner_sub = sub
