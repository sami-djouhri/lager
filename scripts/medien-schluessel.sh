#!/usr/bin/env bash
# Legt den Schluessel zwischen Lager und medien an (Stufe 5, Filme & Medien).
#
#   bash scripts/medien-schluessel.sh
#
# Schreibt denselben Zufallswert an zwei Stellen und gibt ihn NIE aus:
#   * medien:  ~/docker/medien/secrets/lager_token   (Rechte 600, eingehaengt
#              nach /run/secrets/medien/lager_token)
#   * lager:   eine Zeile MEDIEN_TOKEN=... in ~/docker/lager/.env
#
# Danach beide Dienste neu starten, damit sie den Wert lesen:
#   (cd ~/docker/medien && docker compose up -d) && (cd ~/docker/lager && docker compose up -d)
#
# Laeuft ein zweites Mal nicht drueber: steht schon ein Schluessel an einer der
# beiden Stellen, bricht es ab, statt einen der beiden zu ersetzen und die
# Anbindung still zu trennen.
set -euo pipefail

LAGER="$(cd "$(dirname "$0")/.." && pwd)"
MEDIEN="${MEDIEN_DIR:-$LAGER/../medien}"
DATEI="$MEDIEN/secrets/lager_token"
ENV="$LAGER/.env"

[[ -d "$MEDIEN/secrets" ]] || { echo "FEHLER: $MEDIEN/secrets fehlt" >&2; exit 1; }
if [[ -s "$DATEI" ]]; then
  echo "Abbruch: $DATEI gibt es schon. Zum Erneuern erst beide Stellen leeren." >&2
  exit 1
fi
if [[ -f "$ENV" ]] && grep -q '^MEDIEN_TOKEN=' "$ENV"; then
  echo "Abbruch: MEDIEN_TOKEN steht schon in $ENV. Zum Erneuern erst beide Stellen leeren." >&2
  exit 1
fi

WERT="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
( umask 077; printf '%s\n' "$WERT" > "$DATEI" )
# Die .env behaelt ihre Rechte; angehaengt wird mit eigenem Zeilenende davor,
# falls die letzte Zeile keines hat.
[[ -f "$ENV" && -s "$ENV" && "$(tail -c1 "$ENV")" != "" ]] && printf '\n' >> "$ENV"
printf 'MEDIEN_TOKEN=%s\n' "$WERT" >> "$ENV"
unset WERT

echo "Schlüssel angelegt: $DATEI und MEDIEN_TOKEN in $ENV (Wert nicht ausgegeben)."
echo "Jetzt beide Dienste neu starten:"
echo "  (cd $MEDIEN && docker compose up -d) && (cd $LAGER && docker compose up -d)"
