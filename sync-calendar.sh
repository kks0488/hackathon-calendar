#!/bin/bash
set -euo pipefail

# Hackathon Calendar → NAS WebDAV + GitHub 동기화
# Usage: ./sync-calendar.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ICS_FILE="$REPO_DIR/hackathon-calendar.ics"
ENV_FILE="$REPO_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

: "${SYNOLOGY_CREDENTIAL_FILE:=$HOME/.config/synology/credentials.env}"
if [ ! -f "$SYNOLOGY_CREDENTIAL_FILE" ] || [ -L "$SYNOLOGY_CREDENTIAL_FILE" ]; then
    echo "Credential file is missing or is not a regular file" >&2
    exit 1
fi
if [ "$(stat -c '%u' "$SYNOLOGY_CREDENTIAL_FILE")" != "$(id -u)" ]; then
    echo "Credential file must be owned by the current user" >&2
    exit 1
fi
case "$(stat -c '%a' "$SYNOLOGY_CREDENTIAL_FILE")" in
    ?00) ;;
    *) echo "Credential file permissions must deny group and other access" >&2; exit 1 ;;
esac
set -a
# shellcheck disable=SC1090
. "$SYNOLOGY_CREDENTIAL_FILE"
set +a

: "${NAS_WEBDAV_URL:?Set NAS_WEBDAV_URL in .env}"
: "${NAS_WEBDAV_USER:?Set NAS_WEBDAV_USER in the credential file}"
: "${NAS_WEBDAV_PASSWORD:?Set NAS_WEBDAV_PASSWORD in the credential file}"

echo "=== Hackathon Calendar Sync ==="

# 1. NAS WebDAV 업로드
echo -n "[1/2] NAS WebDAV 업로드... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -T "$ICS_FILE" \
    --user "${NAS_WEBDAV_USER}:${NAS_WEBDAV_PASSWORD}" "$NAS_WEBDAV_URL")
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "OK ($HTTP_CODE)"
else
    echo "FAIL ($HTTP_CODE)"
fi

# 2. GitHub push (optional)
echo -n "[2/2] GitHub push... "
cd "$REPO_DIR"
if [ -d .git ]; then
    git add hackathon-calendar.ics && git commit -m "Update hackathon calendar $(date +%Y-%m-%d)" -q && git push -q 2>/dev/null
    echo "OK"
else
    echo "SKIP (no git repo)"
fi

echo "=== Done ==="
echo "구독 URL: $NAS_WEBDAV_URL"
