#!/usr/bin/env bash
# Haelt die versionierte Typdatei frontend/src/types.generated.ts an der API fest.
#
# Warum es diese Pruefung gibt: die Datei ist erzeugt und trotzdem versioniert.
# Das ist kein Versehen, sondern noetig, weil das Dockerfile `COPY frontend/`
# macht und danach `npm run build`, ohne den Generator aufzurufen. Ignoriert
# war lager aus einem frischen Klon nicht baubar (TS2307: Cannot find module
# './types.generated', gemessen 2026-09-06 auf einem Wirt ohne diesen
# Arbeitsbaum). Eine erzeugte Datei im Repo kann aber still veralten, sobald
# jemand die API aendert und den Generator nicht laufen laesst. Genau das
# faengt dieses Skript ab.
#
# Der Weg: die OpenAPI-Spec aus dem Image erzeugen, daraus die Typdatei neu
# erzeugen, gegen die versionierte diffen.
#
# app/ wird dabei aus dem Arbeitsbaum eingehaengt, wie in run-tests.sh. Sonst
# pruefte das Skript gegen den Quelltext im Image und meldete gruen, solange
# nur das Image alt ist.
#
# Kann es nicht pruefen, endet es mit rc=2 und sagt warum. Es meldet in dem
# Fall bewusst NICHT gruen: ein stiller Fallback verbirgt den Dauerausfall.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-lager-lager}"
TYPDATEI="frontend/src/types.generated.ts"
OPENAPI_TS="frontend/node_modules/.bin/openapi-typescript"

# Diese Flags muessen woertlich in frontend/package.json unter scripts.gen:types
# stehen. Sie werden hier nicht aus package.json abgeleitet, sondern dagegen
# geprueft: laufen beide auseinander, pruefte dieses Skript etwas anderes als
# der Generator erzeugt, und der Unterschied saehe wie echter Drift aus.
FLAGS="--default-non-nullable false"

nicht_pruefbar() {
  echo "NICHT PRUEFBAR: $1" >&2
  echo "Die Typdatei ist damit ungeprueft, nicht in Ordnung." >&2
  exit 2
}

[[ -f "$TYPDATEI" ]] || nicht_pruefbar "$TYPDATEI fehlt im Arbeitsbaum."

docker image inspect "$IMAGE" >/dev/null 2>&1 \
  || nicht_pruefbar "Image '$IMAGE' fehlt. Erst bauen: docker compose build"

[[ -x "$OPENAPI_TS" ]] \
  || nicht_pruefbar "$OPENAPI_TS fehlt. Erst holen: cd frontend && npm ci"

grep -qF -- "$FLAGS" frontend/package.json \
  || nicht_pruefbar "Die Flags '$FLAGS' stehen nicht mehr in frontend/package.json.
  Dieses Skript wuerde mit anderen Optionen erzeugen als der Generator.
  FLAGS in scripts/pruefe-typdatei.sh an scripts.gen:types angleichen."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Ohne Netz und gegen eine leere Datenbank: die Spec haengt an keinem von
# beidem. Der Import meldet dabei eine Warnung zur Owner-Kennung, die hier
# nichts bedeutet und nach stderr geht.
docker run --rm --network none \
  -v "$PWD/app:/app/app:ro" \
  -e DATABASE_URL=sqlite:////tmp/leer.db \
  "$IMAGE" python scripts/generate-openapi.py \
  >"$TMP/openapi.json" 2>"$TMP/spec.log" \
  || { cat "$TMP/spec.log" >&2; nicht_pruefbar "Die Spec liess sich nicht erzeugen."; }

[[ -s "$TMP/openapi.json" ]] || nicht_pruefbar "Die erzeugte Spec ist leer."

"$OPENAPI_TS" "$TMP/openapi.json" $FLAGS -o "$TMP/types.ts" >/dev/null 2>&1 \
  || nicht_pruefbar "openapi-typescript ist gescheitert."

if diff -q "$TMP/types.ts" "$TYPDATEI" >/dev/null; then
  echo "OK: $TYPDATEI ist auf dem Stand der API."
  exit 0
fi

echo "DRIFT: $TYPDATEI passt nicht mehr zur API." >&2
echo >&2
diff -u "$TYPDATEI" "$TMP/types.ts" | head -40 >&2
echo >&2
echo "Neu erzeugen und mit einchecken:" >&2
echo "  cd frontend && npm run gen:types" >&2
exit 1
