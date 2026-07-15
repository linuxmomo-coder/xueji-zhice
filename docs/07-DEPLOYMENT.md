# 学迹智评部署与运维说明书 v0.2

## 1. 服务

Nginx、React前端、FastAPI、PostgreSQL/pgvector、Redis和私有上传卷均由Docker Compose管理。数据库与Redis不映射公网端口。

## 2. 本地开发

```bash
cp .env.example .env
# development可按需开启demo
cd backend && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

完整容器：

```bash
docker compose -f deployment/docker-compose.yml up --build
```

## 3. 生产配置

从`deployment/.env.production.example`创建服务器`.env`：

- `APP_ENV=production`
- `SECRET_KEY`不少于32位随机值；
- 强数据库密码；
- 正式HTTPS域名CORS；
- `ENABLE_DEMO=false`
- `SEED_DEMO_DATA=false`
- `AUTO_CREATE_SCHEMA=false`

不满足条件时后端必须退出，而不是带弱默认值继续运行。

## 4. 发布流程

```text
feature/release branch
→ Pull Request
→ backend tests + coverage + ruff + bandit
→ Alembic升降级演练
→ frontend TypeScript/Vite build
→ Docker Compose和镜像构建
→ 人工批准production environment
→ SSH部署
→ 数据库备份
→ alembic upgrade head
→ docker compose up -d
→ /health检查
```

仓库提供`.github/workflows/deploy.yml`，需要GitHub Environment `production` 和Secrets：

- `SERVER_HOST`
- `SERVER_USER`
- `SERVER_SSH_KEY`
- `DEPLOY_PATH`

## 5. 部署命令

服务器执行：

```bash
cd /opt/xueji-zhice
bash deployment/deploy.sh
```

脚本负责拉取、备份提示、迁移、启动和健康检查。首次上线前必须人工演练数据库恢复。

## 6. HTTPS与安全头

Nginx生产层需配置证书、HTTP到HTTPS跳转、HSTS、X-Content-Type-Options、Referrer-Policy、合理CSP和API限流。

## 7. 备份

- PostgreSQL每日全量，7个日备份、4个周备份；
- 私有上传文件异地备份；
- 迁移前额外生成发布快照；
- 每季度执行恢复演练并记录RTO/RPO。

## 8. 回滚

应用回滚优先切回上一镜像/提交；数据库避免直接downgrade破坏数据，使用向前修复迁移或备份恢复。健康检查失败时停止切流并保留日志和request_id。

## 9. 可观测性

至少采集：API状态码和P95、request_id、登录失败、跨家庭拒绝、迁移版本、文件上传失败、练习判分耗时、OCR/AI任务成功率、磁盘和备份状态。日志禁止保存密码、令牌、完整学生原始资料和密钥。
