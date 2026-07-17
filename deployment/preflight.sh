#!/bin/sh
set -eu

APP_DIR=${APP_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
ENV_FILE=${ENV_FILE:-$APP_DIR/.env}
COMPOSE_FILE=${COMPOSE_FILE:-$APP_DIR/deployment/docker-compose.yml}

fail() {
  echo "[preflight] ERROR: $1" >&2
  exit 1
}

require_value() {
  name=$1
  eval "value=\${$name:-}"
  [ -n "$value" ] || fail "$name 未配置"
  case "$value" in
    CHANGE_ME|change-me|change-me-in-production|REPLACE_AT_DEPLOYMENT)
      fail "$name 仍为占位值"
      ;;
  esac
}

[ -f "$ENV_FILE" ] || fail "缺少生产环境文件 $ENV_FILE"
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

[ "${APP_ENV:-}" = "production" ] || fail "APP_ENV 必须为 production"
[ "${ENABLE_DEMO:-false}" = "false" ] || fail "生产环境禁止 ENABLE_DEMO"
[ "${SEED_DEMO_DATA:-false}" = "false" ] || fail "生产环境禁止 SEED_DEMO_DATA"
[ "${AUTO_CREATE_SCHEMA:-false}" = "false" ] || fail "生产环境禁止 AUTO_CREATE_SCHEMA"
[ "${ENABLE_API_DOCS:-false}" = "false" ] || fail "生产环境必须关闭 API 文档"

for name in SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD DATABASE_URL REDIS_URL CORS_ORIGINS FRONTEND_PUBLIC_URL STORAGE_BUCKET STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SMTP_HOST SMTP_FROM_EMAIL; do
  require_value "$name"
done

[ "${#SECRET_KEY}" -ge 32 ] || fail "SECRET_KEY 长度必须不少于32位"
case "$DATABASE_URL" in
  postgresql*|postgres*) ;;
  *) fail "DATABASE_URL 必须使用 PostgreSQL" ;;
esac
case "$CORS_ORIGINS" in
  *\**) fail "CORS_ORIGINS 禁止通配符" ;;
esac
case "$FRONTEND_PUBLIC_URL" in
  https://*) ;;
  *) fail "FRONTEND_PUBLIC_URL 必须使用 HTTPS" ;;
esac
[ "${STORAGE_PROVIDER:-}" = "s3" ] || fail "生产环境 STORAGE_PROVIDER 必须为 s3"
[ "${REQUIRE_EMAIL_VERIFICATION:-false}" = "true" ] || fail "生产环境必须开启邮箱验证"
[ "${EMAIL_PROVIDER:-}" = "smtp" ] || fail "生产环境必须使用 SMTP 邮件服务"

if [ "${OCR_ENABLED:-false}" = "true" ]; then
  [ "${OCR_PROVIDER:-}" = "paddle_http" ] || fail "OCR_PROVIDER 必须为 paddle_http"
  require_value OCR_SERVICE_URL
  require_value OCR_SERVICE_TOKEN
  case "$OCR_SERVICE_URL" in
    https://*) ;;
    *) fail "OCR_SERVICE_URL 必须使用 HTTPS" ;;
  esac
fi

if [ "${AI_ENABLED:-false}" = "true" ]; then
  case "${AI_PRIMARY_PROVIDER:-}" in
    bailian_openai)
      require_value DASHSCOPE_API_KEY
      ;;
    hunyuan_openai)
      require_value HUNYUAN_API_KEY
      ;;
    *) fail "AI_PRIMARY_PROVIDER 未配置为受支持的真实提供方" ;;
  esac
  case "${AI_FALLBACK_PROVIDER:-disabled}" in
    disabled) ;;
    bailian_openai) require_value DASHSCOPE_API_KEY ;;
    hunyuan_openai) require_value HUNYUAN_API_KEY ;;
    *) fail "AI_FALLBACK_PROVIDER 配置无效" ;;
  esac
fi

command -v docker >/dev/null 2>&1 || fail "未安装 Docker"
docker compose version >/dev/null 2>&1 || fail "未安装 Docker Compose 插件"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null

echo "[preflight] OK: 生产配置、对象存储、邮件、OCR/AI条件配置和Compose结构检查通过"
echo "[preflight] NOTICE: 当前Compose内部监听HTTP，公网HTTPS必须由腾讯云负载均衡、Caddy、Traefik或其他可信反向代理终止。"
