"""Fachliche Messwerte des Lagers fuer Prometheus.

Warum es diese Datei gibt: ``/metrics`` lieferte bis zum 2026-10-24 genau
20 Metrik-Familien, und alle zwanzig waren technisch -- HTTP-Dauer,
Antwortgroesse, offene Dateizeiger, Python-Garbage-Collector. Der Dienst war
damit lueckenlos daraufhin beobachtet, ob er *antwortet*, und auf keiner Seite
daraufhin, ob er *etwas zu sagen hat*.

Gemessen an dem Tag: die Datenbank war ein Seed vom 2026-02-26 (alle 20
Produkte und 24 Posten in derselben Sekunde angelegt), die juengste Buchung war
vom 2026-03-01, und jeder einzelne Posten im Regal war seit 210 bis 243 Tagen
abgelaufen. ``/api/critical`` hatte diesen Stand 793 mal an das Briefing
geliefert. Nichts davon war rot, denn ein Dienst, der acht Monate alte Daten
ausliefert, ist technisch vollkommen gesund.

Der Anker ist ``lager_buchungen``: er existiert auch als 0. Eine Alarmregel
kann nicht auf eine fehlende Zeitreihe feuern, und ein leeres Lager hat von
sich aus keine Alterskennzahl (Memory
interne Notiz). Die Altersmetriken fehlen
deshalb bewusst, solange es nichts zu altern gibt -- die Regeln knuepfen am
Anker an und fragen das Alter nur, wenn der Anker ueber 0 steht. Ein frisch
aufgesetztes Lager ist nicht krank.

Gelesen wird mit rohem SQL an der Engine, nicht ueber das ORM. Das
Mandanten-Scoping aus ``app/tenant.py`` haengt global in der Session und wuerde
jede dieser Zahlen auf ``DEFAULT_OWNER_SUB`` einschraenken -- eine
Betriebskennzahl ueber "einen von mehreren Mandanten" sieht aber genauso aus
wie eine ueber das ganze Haus und wird beim zweiten Mandanten still falsch.

⚠️ **Keine Produktnamen, keine Kategorien, keine Mandanten-Kennungen in den
Labels.** Metriken landen in einer zweiten Datenbank, gehen ueber den
Alarmtext in Push-Nachrichten und sind von jedem lesbar, der Prometheus
erreicht. Was hier steht, sind ausschliesslich Anzahlen. Die Zahl der
Mandanten ist eine Anzahl, ihre Kennungen waeren es nicht.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import text

from app.db import engine
from app.logging import get_logger

logger = get_logger("lager.messwerte")

# Eine Abfrage je Kennzahl, absichtlich einzeln und ohne Verschachtelung: das
# sind COUNTs auf vier kleinen Tabellen, und wer hier spaeter etwas aendert,
# soll die Zeile lesen koennen, die die Zahl erzeugt.
_ZAEHLER: tuple[tuple[str, str, str], ...] = (
    (
        "lager_produkte",
        "Angelegte Produkte (Stammdaten, alle Mandanten).",
        "SELECT COUNT(*) FROM product",
    ),
    (
        "lager_produkte_mit_mindestbestand",
        (
            "Produkte mit gesetztem min_stock. Ohne Mindestbestand laufen die "
            "Unterbestands-Pfade leer: /api/stats/low-stock antwortet mit einer "
            "leeren Liste und sieht dabei gesund aus."
        ),
        "SELECT COUNT(*) FROM product WHERE min_stock IS NOT NULL AND min_stock > 0",
    ),
    (
        "lager_posten",
        "Posten mit Restmenge groesser 0 (alle Mandanten).",
        "SELECT COUNT(*) FROM stock_entry WHERE quantity > 0",
    ),
    (
        "lager_posten_abgelaufen",
        (
            "Posten mit Restmenge, deren MHD in der Vergangenheit liegt. Noch im "
            "Regal, also kein gebuchter Verlust."
        ),
        (
            "SELECT COUNT(*) FROM stock_entry WHERE quantity > 0 AND mhd IS NOT NULL "
            "AND mhd < date('now')"
        ),
    ),
    (
        "lager_posten_ohne_mhd",
        (
            "Posten mit Restmenge und ohne MHD. Sie koennen in keiner Ablauf-Sicht "
            "auftauchen, auch nicht faelschlich."
        ),
        "SELECT COUNT(*) FROM stock_entry WHERE quantity > 0 AND mhd IS NULL",
    ),
    (
        "lager_buchungen",
        (
            "Verbrauchsbuchungen insgesamt. Anker dieser Messkette: existiert auch "
            "als 0, damit eine Regel daran haengen kann."
        ),
        "SELECT COUNT(*) FROM consumption_event",
    ),
    (
        "lager_geraete",
        "Erfasste Elektronik-Posten (alle Mandanten).",
        "SELECT COUNT(*) FROM electronic_asset",
    ),
    (
        "lager_mandanten",
        "Zahl der Mandanten mit mindestens einem Produkt. Nur die Anzahl, nie die Kennungen.",
        "SELECT COUNT(DISTINCT owner_sub) FROM product",
    ),
)

# Altersangaben. Fehlt die Grundlage, fehlt die Metrik: 0 hiesse "gerade
# passiert" und waere die genaue Umkehrung der Wahrheit.
_ALTER: tuple[tuple[str, str, str], ...] = (
    (
        "lager_letzte_buchung_alter_sekunden",
        (
            "Alter der juengsten Verbrauchsbuchung. Fehlt, wenn nie gebucht wurde "
            "-- dann sagt lager_buchungen 0."
        ),
        (
            "SELECT CAST(strftime('%s','now') - strftime('%s', MAX(consumed_at)) AS INTEGER) "
            "FROM consumption_event"
        ),
    ),
    (
        "lager_letzter_posten_alter_sekunden",
        (
            "Alter des juengsten eingebuchten Postens. Fehlt, wenn nie eingebucht "
            "wurde -- dann sagt lager_posten 0."
        ),
        (
            "SELECT CAST(strftime('%s','now') - strftime('%s', MAX(created_at)) AS INTEGER) "
            "FROM stock_entry"
        ),
    ),
)


class LagerSammler:
    """Rechnet die fachlichen Zahlen bei jedem Scrape frisch aus.

    Ein Scrape kostet rund ein Dutzend COUNTs auf einer SQLite-Datei. Das ist
    guenstiger als ein Zwischenspeicher, der nach einem Neustart erst wieder
    gefuellt werden muss und in der Zwischenzeit eine veraltete Zahl als
    aktuelle Messung ausliefert.

    Die Engine ist uebergebbar, damit ein Test gegen seine eigene
    In-Memory-Datenbank messen kann. Die Suite ersetzt ``get_db`` und laesst
    ``app.db.engine`` unberuehrt -- ohne diesen Haken wuerde ein Test die
    Produktionsdatei messen und sein Ergebnis haenge daran, was dort gerade
    drinsteht.
    """

    def __init__(self, quelle=None):
        self._quelle = quelle

    def collect(self):
        quelle = self._quelle if self._quelle is not None else engine
        try:
            with quelle.connect() as conn:
                zaehler = [
                    (name, hilfe, conn.execute(text(sql)).scalar())
                    for name, hilfe, sql in _ZAEHLER
                ]
                alter = [
                    (name, hilfe, conn.execute(text(sql)).scalar())
                    for name, hilfe, sql in _ALTER
                ]
        except Exception as exc:
            # ⚠️ Keine Ausnahme nach draussen: ein werfender Collector nimmt
            # /metrics komplett mit, und dann fehlen auch die technischen
            # Metriken. Der Ausfall wird gemeldet, statt alles zu verdecken.
            #
            # Warnung mit dem Grund in einer Zeile, bewusst kein
            # `logger.exception`. `prometheus_client.register()` ruft `collect()`
            # einmal beim Anmelden auf, um Namensdubletten zu finden -- beim
            # Erststart ist das VOR der ersten Migration, und ein
            # fuenfzigzeiliger SQLAlchemy-Traceback ueber "no such table:
            # product" liest sich dann wie ein Defekt, obwohl nur die
            # Reihenfolge stimmt. Fuer die Diagnose zaehlt die Meldung
            # ("no such table", "database is locked", "disk full"), nicht der
            # Weg durch SQLAlchemy. Der Dauerzustand haengt ohnehin an
            # `lager_messwerte_ok`, nicht am Log.
            logger.warning("messwerte_nicht_lesbar", grund=str(exc).splitlines()[0])
            yield GaugeMetricFamily(
                "lager_messwerte_ok",
                "1 wenn die fachlichen Zahlen gelesen werden konnten, sonst 0.",
                value=0,
            )
            return

        yield GaugeMetricFamily(
            "lager_messwerte_ok",
            "1 wenn die fachlichen Zahlen gelesen werden konnten, sonst 0.",
            value=1,
        )
        for name, hilfe, wert in zaehler:
            yield GaugeMetricFamily(name, hilfe, value=int(wert or 0))
        for name, hilfe, wert in alter:
            if wert is None:
                continue
            yield GaugeMetricFamily(name, hilfe, value=max(0, int(wert)))


def registriere(
    registry: CollectorRegistry | None = None, quelle=None
) -> LagerSammler:
    """Haengt den Sammler in eine Registry (Vorgabe: die globale von prometheus_client)."""
    sammler = LagerSammler(quelle)
    if registry is None:
        from prometheus_client import REGISTRY

        registry = REGISTRY
    registry.register(sammler)
    return sammler
