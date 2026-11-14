#!/usr/bin/env bash
# Copies HA backups out of the container config volume into ~/homeassistant/backups (keeps 14 days).
# Run daily from the user crontab. Undo: crontab -e and delete the line.
set -euo pipefail
SRC="$HOME/homeassistant/config/backups"; DST="$HOME/homeassistant/backups"
mkdir -p "$DST"; [ -d "$SRC" ] || exit 0
rsync -a --chmod=D700,F600 "$SRC"/ "$DST"/
find "$DST" -name '*.tar' -mtime +14 -delete
