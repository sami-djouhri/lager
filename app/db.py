from contextlib import contextmanager

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.backend_auth import sub_from_bearer
from app.config import settings
from app.tenant_auth import loese_owner_sub

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    # Disable pysqlite's own transaction handling so SQLAlchemy (and our
    # event hooks) can fully control BEGIN / COMMIT / ROLLBACK.
    dbapi_conn.isolation_level = None


@event.listens_for(engine, "begin")
def _do_begin(conn):
    """Emit the appropriate BEGIN variant.

    By default we emit plain BEGIN (DEFERRED).  When the ``immediate``
    execution option is set on the connection, we emit BEGIN IMMEDIATE
    instead (pessimistic write lock for SQLite).
    """
    if conn._execution_options.get("immediate", False):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        conn.exec_driver_sql("BEGIN")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db(request: Request) -> Session:  # type: ignore[misc]
    # Tenant an die Session binden. Drei Pfade:
    #  1. Nativer Client: `Authorization: Bearer <HS256-JWT>` (aud=lager-api) →
    #     fail-closed verifiziert (jeder Fehler = 401, KEIN Default-Fallback);
    #     noetig sobald lager oeffentlich (lager-api.saganta.de) erreichbar ist.
    #  2. Web via app-proxy: `X-Saganta-Sub`-Header (better-auth-sub), seit
    #     2026-09-05 mit HMAC-Signatur pruefbar (app/tenant_auth.py, Befund
    #     FCS-01). Vorher war das der einzige Pfad ohne jede Pruefung: wer
    #     :8095 direkt erreichte, konnte sich als beliebiger Mandant ausgeben.
    #  3. Interne/headerlose Aufrufe (life-ops /api/critical, assets-api) →
    #     DEFAULT_OWNER_SUB = bisheriges Verhalten.
    # Das globale do_orm_execute/before_flush (app/tenant.py) liest
    # session.info["owner_sub"]. Auth-Check bewusst VOR SessionLocal(), damit ein
    # 401 keine offene Session hinterlaesst.
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        owner_sub = sub_from_bearer(authorization)
    else:
        owner_sub = loese_owner_sub(request)

    db = SessionLocal()
    db.info["owner_sub"] = owner_sub
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


@contextmanager
def begin_immediate(db: Session):
    """Run a block inside a SQLite BEGIN IMMEDIATE transaction.

    SQLite's default transaction mode is DEFERRED, which only acquires a
    write lock when the first write statement is executed.  For the FIFO
    consume flow we need the read-check-modify cycle to be atomic: no
    concurrent connection should be able to read stale quantities while
    we are in the middle of consuming stock.

    BEGIN IMMEDIATE acquires a RESERVED lock right away, preventing other
    connections from writing (and from starting their own IMMEDIATE
    transaction) until we COMMIT or ROLLBACK.  In WAL mode readers are
    still served concurrently.

    The busy_timeout PRAGMA (set on connect) makes concurrent callers
    wait up to 5 s instead of failing immediately with SQLITE_BUSY.

    Usage in a route handler::

        with begin_immediate(db):
            events = svc.consume(...)
        return [ConsumptionEventOut.model_validate(e) for e in events]
    """
    # Ensure we start from a clean state: no pending autobegun transaction.
    if db.in_transaction():
        db.rollback()

    # Force the Session to acquire a connection with the ``immediate``
    # execution option *before* autobegin fires.  This causes the
    # ``begin`` event handler to emit BEGIN IMMEDIATE instead of a plain
    # BEGIN.
    db.connection(execution_options={"immediate": True})
    try:
        yield
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
