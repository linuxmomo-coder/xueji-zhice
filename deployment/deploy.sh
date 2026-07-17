#!/bin/sh
set -eu

APP_DIR=${APP_DIR:-/opt/xueji-zhice}
BACKUP_DIR=${BACKUP_DIR:-$APP_DIR/backups}
COMPOSE="docker compose --env-file .env -f deployment/docker-compose.yml"
cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"

PREVIOUS_SHA=$(git rev-parse HEAD 2>/dev/null || true)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_${TIMESTAMP}.sql"

if $COMPOSE ps postgres >/dev/null 2>&1; then
  $COMPOSE exec -T postgres pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" > "$BACKUP_FILE"
  test -s "$BACKUP_FILE" || {
    echo "数据库备份为空，终止部署" >&2
    exit 1
  }
fi

git fetch --all --prune
git checkout main
git pull --ff-only origin main
NEW_SHA=$(git rev-parse HEAD)

sh deployment/preflight.sh

echo "Deploying $NEW_SHA (previous: ${PREVIOUS_SHA:-none})"
$COMPOSE build --pull
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE up -d --remove-orphans

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    echo "Deployment healthy: $NEW_SHA"
    find "$BACKUP_DIR" -type f -name 'postgres_*.sql' -mtime +30 -delete || true
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
  echo "Application containers restored to $PREVIOUS_SHA. Database backup: $BACKUP_FILE" >&2
  echo "如迁移导致数据库不兼容，请按审批流程执行 deployment/restore-postgres.sh。" >&2
else
  echo "No previous commit is available for automatic application rollback." >&2
fi
exit 1
