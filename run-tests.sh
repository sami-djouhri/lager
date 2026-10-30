#!/usr/bin/env bash
# Testlauf des Lagers.
#
# Gelaufen wird in einem Wegwerf-Container aus dem GEBAUTEN Image, nicht gegen
# eine Host-Umgebung. Das ist Absicht und folgt der Lehre aus dem Saganta-Lauf
# vom 30.08.2026: ein Test gegen den Quellbaum beweist, dass die Datei stimmt,
# nicht dass der laufende Dienst sie hat.
#
# pytest und httpx gehoeren bewusst NICHT ins Produktionsimage. Sie werden fuer
# den Lauf nach /tmp installiert, wie es der Kalender vormacht. Faellt die
# Installation aus (kein Netz), bricht der Lauf ab, statt stillschweigend
# weniger Tests zu sammeln.
#
# Erwartung: "113 passed" oder mehr. Laeuft eine kleinere Zahl durch, wurde ein
# Modul still uebersprungen. Das ist nicht als gruen zu verbuchen.
#
# Danach laeuft scripts/pruefe-typdatei.sh. Es haelt die versionierte
# frontend/src/types.generated.ts an der API fest und braucht Node, deshalb
# laeuft es auf dem Wirt statt im Container. Beide Teile laufen immer, auch
# wenn der erste faellt: sonst verdeckt ein Fehler den anderen.
set -uo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-lager-lager}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:  docker compose build"
  exit 1
fi

# tests MUSS unter /app/tests liegen: die Suite importiert `tests.conftest`.
# --user 0:0 nur fuer den Lauf, die Rechte im Quellbaum bleiben unberuehrt.
docker run --rm --user 0:0 \
  -v "$PWD/tests:/app/tests:ro" \
  -v "$PWD/app:/app/app:ro" \
  -w /app \
  -e PYTHONPATH=/tmp/p:/app \
  "$IMAGE" \
  sh -c 'pip install -q --target /tmp/p pytest httpx || exit 1
         python -m pytest tests -q -p no:cacheprovider'
RC_PYTEST=$?

echo
echo "--- Typdatei gegen die API ---"
IMAGE="$IMAGE" bash scripts/pruefe-typdatei.sh
RC_TYPEN=$?

echo
if [[ $RC_PYTEST -eq 0 && $RC_TYPEN -eq 0 ]]; then
  echo "Alles gruen."
  exit 0
fi
[[ $RC_PYTEST -ne 0 ]] && echo "Testlauf: rc=$RC_PYTEST"
[[ $RC_TYPEN -ne 0 ]] && echo "Typdatei: rc=$RC_TYPEN (2 = konnte nicht pruefen)"
exit 1
