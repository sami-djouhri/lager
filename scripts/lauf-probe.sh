#!/usr/bin/env bash
# Klickt Einbuch- und Lagern-Lauf in einer Wegwerf-Instanz durch (Stufe 4).
#
#   bash scripts/lauf-probe.sh [bilderordner]
#
# Nie gegen den echten Bestand: die Probe legt an, bucht und laedt Fotos
# hoch. Die Instanz kommt aus dem gebauten Image (`docker compose build`),
# mit leerer Datenbank im Container und OHNE Demo-Daten (deren Strichcodes
# kollidieren mit denen der Probe).
#
# Das Netz ist `--internal`: kein Weg nach draussen. Die Instanz fragt bei
# einem unbekannten Strichcode OpenFoodFacts, und eine Probe soll keinen
# fremden Dienst mit Testcodes beschaeftigen. Der Ausfall dort ist zugleich
# ein Testfall (der Lauf muss ohne Vorschlag weitergehen).
#
# Aufruf: `bash scripts/lauf-probe.sh`.
#
# Danach ist alles wieder weg; die Bilder bleiben im Ordner und gehoeren
# angesehen, nicht nur gezaehlt.
set -uo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-lager-lager}"
BILDER="${1:-$(mktemp -d /tmp/lager-lauf-probe-XXXX)}"
NAME="lager-lauf-probe-$$"
NETZ="lager-lauf-probe-$$"
mkdir -p "$BILDER"

aufraeumen() {
  docker rm -f "$NAME" >/dev/null 2>&1
  docker network rm "$NETZ" >/dev/null 2>&1
}
trap aufraeumen EXIT

# Eigenes Subnetz (Root-Policy: nie Auto-Vergabe, sie kann das LAN ueberdecken).
# Das erste freie aus 10.212.250.0/24 in /28-Stuecken: mit einem festen Netz
# scheiterte ein zweiter Lauf, solange der erste noch lief (gemessen 2026-11-01,
# „Pool overlaps with other one").
NETZ_OK=0
for teil in 0 16 32 48 64 80 96 112; do
  if docker network create --internal --subnet "10.212.250.$teil/28" "$NETZ" >/dev/null 2>&1; then
    NETZ_OK=1; break
  fi
done
[[ $NETZ_OK -eq 1 ]] || { echo "FEHLER: kein freies Probe-Subnetz in 10.212.250.0/24" >&2; exit 2; }
docker run -d --name "$NAME" --network "$NETZ" \
  -e DEFAULT_OWNER_SUB=probe -e EVENT_EMISSION_ENABLED=false -e OPENFOODFACTS_TIMEOUT_SEC=1 \
  -e DATABASE_URL=sqlite:////app/data/probe.db \
  --entrypoint sh "$IMAGE" -c 'alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000' \
  >/dev/null || exit 2

for _ in $(seq 1 40); do
  docker exec "$NAME" python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    >/dev/null 2>&1 && break
  sleep 0.5
done

mkdir -p "$BILDER/bilder"
cp scripts/lauf-probe.js "$BILDER/lauf-probe.js"
chmod -R a+rwX "$BILDER"
docker run --rm --network "container:$NAME" -v "$BILDER:/work" \
  -e NODE_PATH=/usr/src/app/node_modules -w /work --entrypoint node \
  zenika/alpine-chrome:with-puppeteer lauf-probe.js
RC=$?
echo "Bilder: $BILDER/bilder"
exit $RC
