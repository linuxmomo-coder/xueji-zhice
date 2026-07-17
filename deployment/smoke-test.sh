#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-}
[ -n "$BASE_URL" ] || {
  echo "用法: BASE_URL=https://your-domain.example sh deployment/smoke-test.sh" >&2
  exit 2
}

case "$BASE_URL" in
  https://*) ;;
  *) echo "BASE_URL 必须使用 HTTPS" >&2; exit 2 ;;
esac

request_code() {
  path=$1
  curl -sS -o /tmp/xueji-smoke-body -w "%{http_code}" --max-time 20 "$BASE_URL$path"
}

health_code=$(request_code /health)
[ "$health_code" = "200" ] || {
  echo "健康检查失败: HTTP $health_code" >&2
  cat /tmp/xueji-smoke-body >&2 || true
  exit 1
}

grep -q '"status":"ok"' /tmp/xueji-smoke-body || {
  echo "健康检查响应格式异常" >&2
  cat /tmp/xueji-smoke-body >&2
  exit 1
}

for path in /docs /redoc /openapi.json /api/v1/demo/accounts; do
  code=$(request_code "$path")
  case "$code" in
    404|403) ;;
    *)
      echo "生产禁用检查失败: $path 返回 HTTP $code" >&2
      exit 1
      ;;
  esac
done

unauthorized_code=$(request_code /api/v1/students)
[ "$unauthorized_code" = "401" ] || {
  echo "未认证访问控制异常: /api/v1/students 返回 HTTP $unauthorized_code" >&2
  exit 1
}

echo "[smoke] OK: HTTPS健康检查、生产接口关闭和未认证访问控制均通过"
