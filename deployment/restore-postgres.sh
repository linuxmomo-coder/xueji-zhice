#!/bin/sh
set -eu

APP_DIR=${APP_DIR:-/opt/xueji-zhice}
BACKUP_FILE=${1:-}
COMPOSE="docker compose --env-file .env -f deployment/docker-compose.yml"

[ -n "$BACKUP_FILE" ] || {
  echo "用法: sh deployment/restore-postgres.sh /absolute/path/backup.sql" >&2
  exit 2
}
[ -f "$BACKUP_FILE" ] || {
  echo "备份文件不存在: $BACKUP_FILE" >&2
  exit 2
}

cd "$APP_DIR"
[ -f .env ] || {
  echo "缺少 $APP_DIR/.env" >&2
  exit 2
}

set -a
# shellcheck disable=SC1091
. ./.env
set +a

[ "${APP_ENV:-}" = "production" ] || {
  echo "仅允许在明确配置 APP_ENV=production 的目标环境执行" >&2
  exit 2
}

if [ "${CONFIRM_RESTORE:-}" != "YES_RESTORE_XUEJI" ]; then
  echo "恢复会覆盖当前数据库。确认后执行:" >&2
  echo "CONFIRM_RESTORE=YES_RESTORE_XUEJI sh deployment/restore-postgres.sh $BACKUP_FILE" >&2
  exit 2
fi

$COMPOSE stop backend ocr-worker ai-worker regrade-worker
$COMPOSE exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB}' AND pid <> pg_backend_pid();"
$COMPOSE exec -T postgres dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
$COMPOSE exec -T postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_FILE"
$COMPOSE up -d backend ocr-worker ai-worker regrade-worker

echo "数据库恢复完成。请立即执行: BASE_URL=https://your-domain sh deployment/smoke-test.sh"
