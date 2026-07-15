#!/bin/sh
set -eu

APP_DIR=${APP_DIR:-/opt/xueji-zhice}
cd "$APP_DIR"

git fetch --all --prune
git checkout main
git pull --ff-only origin main

docker compose --env-file .env -f deployment/docker-compose.yml build
docker compose --env-file .env -f deployment/docker-compose.yml run --rm backend alembic upgrade head
docker compose --env-file .env -f deployment/docker-compose.yml up -d --remove-orphans

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    echo "Deployment healthy"
    exit 0
  fi
  sleep 2
done

echo "Health check failed" >&2
docker compose --env-file .env -f deployment/docker-compose.yml ps >&2
exit 1
