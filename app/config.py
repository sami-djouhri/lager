from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"

    # OpenFoodFacts
    OPENFOODFACTS_TIMEOUT_SEC: int = 3

    # Mandant fuer headerlose interne Aufrufer (life-ops, assets-api).
    #
    # ★ Leer als Vorbelegung, seit 2026-09-05. Vorher stand hier die Kennung
    # eines konkreten Menschen. Sie gehoert nicht in ein Repo, das
    # veroeffentlicht werden soll, und ein Selbsthoster hat ohnehin eine andere.
    # Wert kommt aus .env, eingetragen von
    # saganta/scripts/owner-kennung-eintragen.sh.
    #
    # Leer heisst fail-closed: headerlose Aufrufe sehen dann nichts, statt
    # stillschweigend die Daten irgendeines Kontos zu sehen. Beim Start wird
    # einmal gewarnt (app/main.py), damit der Zustand nicht unbemerkt bleibt.
    DEFAULT_OWNER_SUB: str = ""

    # Native Apps: HS256-Backend-JWT (aud=lager-api) vom saganta-auth-service.
    # Muss == SAGANTA_BACKEND_SECRET des auth-service sein (Wert NUR in der .env des Wirts).
    # Leer => Bearer-Auth deaktiviert (nur Header/Default-Pfad, bisheriges Verhalten).
    SAGANTA_BACKEND_SECRET: str = ""

    # Echtheitsnachweis fuer den X-Saganta-Sub-Header (app/tenant_auth.py).
    # Eigenes Geheimnis je Dienst: wer das Lager lesen darf, soll damit nicht
    # automatisch Kalender und Post lesen duerfen.
    # Leer => bisheriges Verhalten, Header gilt ungeprueft.
    # TENANT_HEADER_ENFORCE: 0 = beobachten und protokollieren, 1 = 401 erzwingen.
    # Erst scharf schalten, wenn die Protokolle ueber Tage still bleiben.
    LAGER_TENANT_SECRET: str = ""
    TENANT_HEADER_ENFORCE: int = 0

    # marktwatch (node1, cross-host → Host-IP; Container-DNS gilt nur same-network)
    # Optionale Anbindung an marktwatch (Marktwert von Elektronik). Leer =
    # Merkmal aus, der Marktwert bleibt dann leer. Adresse gehoert in die .env:
    # sie zeigt auf einen Rechner, den es nur in dieser Installation gibt.
    MARKTWATCH_BASE_URL: str = ""
    MARKTWATCH_TIMEOUT_SEC: float = 30.0
    # X-API-Key für marktwatch; Wert liegt NUR in der host-kanonischen .env
    MARKTWATCH_API_KEY: str = ""
    MARKTWATCH_CACHE_TTL_MINUTES: int = 720
    # Marktwert >= Threshold + nicht in aktiver Nutzung => Verkaufsempfehlung (Portfolio)
    RESALE_THRESHOLD_EUR: float = 50.0

    # Event Spine (life-ops-api POST /api/events)
    LIFE_OPS_URL: str = "http://life-ops-api:8000"
    EVENT_SOURCE: str = "lager"
    EVENT_EMISSION_ENABLED: bool = True
    EVENT_EMIT_TIMEOUT_SEC: float = 2.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
