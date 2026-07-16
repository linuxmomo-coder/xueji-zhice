#!/bin/sh
set -eu

APP_DIR=${APP_DIR:-/opt/xueji-zhice}
BACKUP_DIR=${BACKUP_DIR:-$APP_DIR/backups}
COMPOSE="docker compose --env-file .env -f deployment/docker-compose.yml"
cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"

PREVIOUS_SHA=$(git rev-parse HEAD 2>/dev/null || true)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if $COMPOSE ps postgres >/dev/null 2>&1; then
  $COMPOSE exec -T postgres pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
    > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql"
fi

git fetch --all --prune
git checkout main
git pull --ff-only origin main
NEW_SHA=$(git rev-parse HEAD)

echo "Deploying $NEW_SHA (previous: ${PREVIOUS_SHA:-none})"
$COMPOSE build --pull
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE up -d --remove-orphans

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    echo "Deployment healthy: $NEW_SHA"
    exit 0
  fi
  sleep 2
done

echo "Health check failed; rolling application code back to ${PREVIOUS_SHA:-unknown}" >&2
$COMPOSE ps >&2
if [ -n "${PREVIOUS_SHA:-}" ]; then
  git checkout "$PREVIOUS_SHA"
  $COMPOSE build
  $COMPOSE up -d --remove-orphans
  echo "Application containers restored to $PREVIOUS_SHA. Database backup: $BACKUP_DIR/postgres_${TIMESTAMP}.sql" >&2
else
  echo "No previous commit is available for automatic application rollback." >&2
fi
exit 1
