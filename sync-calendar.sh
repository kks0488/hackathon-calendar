#!/bin/bash
set -euo pipefail

# Hackathon Calendar → NAS WebDAV + GitHub 동기화
# Usage: ./sync-calendar.sh

ICS_FILE="/home/kkaemo/projects/hackathon/hackathon-calendar.ics"
ENV_FILE="/home/kkaemo/projects/hackathon/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

: "${NAS_WEBDAV_URL:?Set NAS_WEBDAV_URL in .env}"
: "${NAS_WEBDAV_USER:?Set NAS_WEBDAV_USER in .env}"
: "${NAS_WEBDAV_PASSWORD:?Set NAS_WEBDAV_PASSWORD in .env}"

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
cd /home/kkaemo/projects/hackathon
if [ -d .git ]; then
    git add hackathon-calendar.ics && git commit -m "Update hackathon calendar $(date +%Y-%m-%d)" -q && git push -q 2>/dev/null
    echo "OK"
else
    echo "SKIP (no git repo)"
fi

echo "=== Done ==="
echo "구독 URL: $NAS_WEBDAV_URL"
