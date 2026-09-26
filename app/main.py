"""Lager – FastAPI application."""

import hmac
import os
import time
import uuid
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes_barcode import router as barcode_router
from app.api.routes_consume import router as consume_router
from app.api.routes_electronics import router as electronics_router
from app.api.routes_products import router as products_router
from app.api.routes_shopping import router as shopping_router
from app.api.routes_stats import critical_router, router as stats_router
from app.api.routes_stock import router as stock_router
from app.db import SessionLocal
from app.domain import DomainError
import app.tenant  # noqa: F401  (registriert das Multi-Tenant-Scoping fuer Session-Events)
from app.logging import configure_logging, get_logger, request_id_var
from app.config import settings
from app.mandant_ableiten import einzigen_mandanten_ableiten
from app.tenant_auth import SIG_HEADER, SUB_HEADER, erwartete_signatur

configure_logging()
logger = get_logger("lager.access")

try:
    APP_VERSION = _pkg_version("lager")
except PackageNotFoundError:
    APP_VERSION = "0.0.0+unknown"

# ---------------------------------------------------------------------------
# In-memory rate limiter: 60 requests per minute per IP
# ---------------------------------------------------------------------------
RATE_LIMIT = 60
RATE_WINDOW = 60  # seconds
_rate_store: dict[str, tuple[int, float]] = {}  # absender -> (count, window_start)
_rate_last_cleanup = time.monotonic()
RATE_CLEANUP_INTERVAL = 300  # 5 minutes

# Ein Nachbardienst, der sich ausweist, bekommt ein eigenes, weiteres
# Kontingent. Begruendung siehe `_absender_und_grenze`.
RATE_LIMIT_DIENST = int(os.environ.get("LAGER_RATE_LIMIT_DIENST", "600"))


def _absender_und_grenze(request: Request) -> tuple[str, int]:
    """Wer fragt hier, und wie viel darf er.

    ★★ Der Deckel von 60 je Minute ist gegen einen durchdrehenden Browser
    gedacht. Er traf am 2026-09-13 aber den Nachbardienst: mealprep baut eine
    Einkaufsliste aus 47 Zutaten und braucht dafuer in Sekunden mehr Anfragen,
    als ein Mensch in einer Minute klickt. Der Rest kam als 429 zurueck, und
    weil der Adapter drueben aus jedem Fehler eine Null macht, entstand eine
    Einkaufsliste aus lauter Nullen, die vollkommen plausibel aussah.

    Ein Nachbardienst laesst sich vom Browser unterscheiden, ohne etwas Neues
    zu erfinden: er schickt ``X-Saganta-Sub`` **mit gueltiger Signatur**, und
    die kann nur erzeugen, wer das Geheimnis dieses Dienstes kennt. Ein
    Browser kennt es nicht. Ohne gesetztes Geheimnis bleibt es fuer alle beim
    alten Wert, also kein stiller Verlust an Schutz.

    Der Nachbardienst bekommt einen **eigenen** Zaehler (``dienst:<sub>``),
    nicht den der IP. Sonst haette der Mensch am selben Rechner sein
    Kontingent an den Dienst verloren, der zufaellig ueber dieselbe Adresse
    kommt.

    ⚠️ Die Signatur haengt am Sub und ist damit wiederholbar. Wer sie abfaengt,
    kann das weitere Kontingent mitbenutzen. Das ist bewusst hingenommen: wer
    sie hat, kann sich ohnehin schon als dieser Mandant ausgeben, und dagegen
    hilft kein Zaehler, sondern nur ein Wechsel des Geheimnisses.
    """
    ip = request.client.host if request.client else "unknown"
    sub = request.headers.get(SUB_HEADER)
    secret = settings.LAGER_TENANT_SECRET
    if sub and secret:
        mitgeschickt = request.headers.get(SIG_HEADER, "")
        if mitgeschickt and hmac.compare_digest(
            mitgeschickt, erwartete_signatur(sub, secret)
        ):
            return f"dienst:{sub}", RATE_LIMIT_DIENST
    return ip, RATE_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("LAGER_RATE_LIMIT_DISABLED") == "1":
            return await call_next(request)

        global _rate_last_cleanup
        absender, grenze = _absender_und_grenze(request)
        now = time.monotonic()

        if now - _rate_last_cleanup > RATE_CLEANUP_INTERVAL:
            stale = [key for key, (_, ws) in _rate_store.items() if now - ws > RATE_WINDOW]
            for key in stale:
                del _rate_store[key]
            _rate_last_cleanup = now

        count, window_start = _rate_store.get(absender, (0, now))
        if now - window_start > RATE_WINDOW:
            count, window_start = 1, now
        else:
            count += 1

        _rate_store[absender] = (count, window_start)

        if count > grenze:
            return JSONResponse(
                {"error": "Zu viele Anfragen. Bitte warte einen Moment."},
                status_code=429,
            )

        return await call_next(request)


class AutheliaHeaderMiddleware(BaseHTTPMiddleware):
    """Liest Authelia-Header (Remote-User/Remote-Groups) in request.state.

    Soft-Auth: wird nur in request.state.user/groups gestempelt und im
    Access-Log mitgeloggt. Keine harte Blockierung: Authelia/Edge-Nginx
    übernimmt die Zugriffskontrolle vor lager. Header werden gesetzt, wenn
    der Request über `*.daheim.home` (Edge-Auth) kommt; bei lokalem
    Direktaufruf (127.0.0.1:8095) sind sie leer.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = request.headers.get("remote-user") or ""
        groups_header = request.headers.get("remote-groups") or ""
        request.state.groups = [g.strip() for g in groups_header.split(",") if g.strip()]
        return await call_next(request)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Setzt Request-ID, emittiert strukturierten Access-Log, propagiert ID in Header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status_code = 500
        response = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = rid
            return response
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                elapsed_ms=elapsed_ms,
                user=getattr(request.state, "user", "") or None,
                groups=getattr(request.state, "groups", None) or None,
            )
            request_id_var.reset(token)


# ★ Einmalige Warnung beim Start, wenn kein Mandant fuer headerlose Aufrufe
# konfiguriert ist. Ohne sie waere der fail-closed-Zustand unsichtbar: interne
# Aufrufer (life-ops, assets-api) bekaemen leere Antworten, und leer sieht aus
# wie "nichts da" statt wie "nicht konfiguriert".
if not settings.DEFAULT_OWNER_SUB:
    _abgeleitet = einzigen_mandanten_ableiten()
    if _abgeleitet:
        settings.DEFAULT_OWNER_SUB = _abgeleitet
        logger.warning(
            "DEFAULT_OWNER_SUB war leer und wurde aus den Daten abgeleitet "
            "(genau ein Mandant vorhanden). Dauerhaft eintragen mit "
            "saganta/scripts/owner-kennung-eintragen.sh"
        )
    else:
        logger.warning(
            "DEFAULT_OWNER_SUB ist leer und nicht ableitbar. Headerlose interne "
            "Aufrufe sehen keine Daten. Eintragen mit "
            "saganta/scripts/owner-kennung-eintragen.sh"
        )

app = FastAPI(title="Lager", version=APP_VERSION)

# Middleware order: last-added is outermost. We want Observability outermost
# (so request_id is set before any other middleware logs), CORS innermost.
app.add_middleware(CORSMiddleware,
    allow_origins=[
        "http://localhost:8095",
        "http://127.0.0.1:8095",
        "http://localhost",
        "https://localhost",
        "https://daheim.home",
        "https://lager.daheim.home",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AutheliaHeaderMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Routers
app.include_router(products_router)
app.include_router(stock_router)
app.include_router(consume_router)
app.include_router(barcode_router)
app.include_router(stats_router)
app.include_router(critical_router)
app.include_router(electronics_router)
app.include_router(shopping_router)

# Prometheus /metrics: muss vor dem SPA-Catchall registriert werden.
Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
    tags=["observability"],
)


@app.get("/health", tags=["health"], include_in_schema=False)
def health_liveness():
    """Liveness: Prozess lebt. Immer 200, kein DB-Hit. K8s/Docker liveness-probe."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/health/ready", tags=["health"], include_in_schema=False)
def health_readiness():
    """Readiness: alle Dependencies (DB) erreichbar. 503 bei Ausfall."""
    return _health_payload()


@app.get("/api/health", tags=["health"])
def api_health():
    return _health_payload()


def _health_payload():
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unavailable"
        return JSONResponse(
            {"status": "error", "db": db_status, "version": APP_VERSION},
            status_code=503,
        )
    return {"status": "ok", "db": db_status, "version": APP_VERSION}


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    logger.warning(
        "domain_error",
        path=request.url.path,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": exc.message,
            "details": exc.details,
            "request_id": request_id_var.get(),
        },
    )


def resolve_spa_path(static_root: Path, path: str) -> Path | None:
    """Loest einen SPA-Anfragepfad auf eine auslieferbare Datei auf.

    `path` kommt URL-dekodiert an: aus `/..%2f..%2fdata%2fapp.db` wird hier
    `../../data/app.db`. Ohne Aufloesen + Wurzel-Check liefert der Fallback jede
    fuer den Prozess lesbare Datei aus (SQLite-DB, /etc/passwd, Quellcode) und
    umgeht damit auch das Tenant-Scoping. Deshalb erst aufloesen (frisst `..`
    und Symlinks), dann gegen die Static-Wurzel pruefen.

    Rueckgabe: die Datei, oder None wenn ausserhalb der Wurzel / nicht vorhanden.
    """
    try:
        candidate = (static_root / path).resolve()
    except OSError:
        return None
    if not candidate.is_relative_to(static_root):
        return None
    return candidate if candidate.is_file() else None


# Serve SPA static files (after all API routers + /metrics)
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    _static_root = _static_dir.resolve()

    @app.get("/manifest.json", include_in_schema=False)
    async def manifest():
        return FileResponse(_static_root / "manifest.json")

    @app.get("/icon-192.png", include_in_schema=False)
    async def icon():
        return FileResponse(_static_root / "icon-192.png")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        file_path = resolve_spa_path(_static_root, path)
        if file_path is not None:
            return FileResponse(file_path)
        return FileResponse(_static_root / "index.html")
