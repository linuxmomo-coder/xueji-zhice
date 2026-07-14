# 学迹智评部署与运维说明书

## 1. 目标环境

MVP 部署于腾讯云 Ubuntu 22.04/24.04，推荐配置 4 核 8GB、100GB 系统盘。使用 Docker Compose 管理服务。

## 2. 服务清单

| 服务 | 端口（容器内） | 公网暴露 |
|---|---:|---:|
| nginx | 80/443 | 是 |
| frontend | 80 | 仅 nginx |
| backend | 8000 | 仅 nginx |
| postgres | 5432 | 否 |
| redis | 6379 | 否 |
| worker | 无 | 否 |

生产环境不得将 PostgreSQL、Redis 或内部管理端口直接暴露公网。

## 3. 环境变量

- `APP_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `FILE_STORAGE_PATH`
- `DASHSCOPE_API_KEY`
- `BAILIAN_MODEL`
- `HUNYUAN_SECRET_ID`
- `HUNYUAN_SECRET_KEY`
- `HUNYUAN_MODEL`
- `OCR_PROVIDER`
- `MAX_UPLOAD_MB`

真实密钥只写入服务器 `.env` 或腾讯云密钥管理服务，不提交 Git。

## 4. 本地启动

```bash
cp .env.example .env
docker compose -f deployment/docker-compose.yml up --build
```

验证：

```bash
curl http://localhost:8000/health
curl http://localhost/api/v1/health
```

## 5. 腾讯云初始化

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git ufw
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

防火墙仅开放：

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 6. 部署步骤

1. 克隆私有仓库或通过部署密钥拉取。
2. 从 `.env.example` 创建 `.env`。
3. 生成强 `SECRET_KEY` 和数据库密码。
4. 启动 PostgreSQL 和 Redis。
5. 执行数据库迁移。
6. 启动 backend、worker、frontend 和 nginx。
7. 检查健康接口和容器日志。
8. 配置域名、HTTPS 和备份。

## 7. HTTPS

域名解析到腾讯云公网 IP 后，使用 Certbot 或腾讯云证书服务。Nginx 强制 HTTP 跳转 HTTPS，并设置安全响应头。

## 8. 数据迁移

使用 Alembic：

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

生产迁移前：

- 备份数据库。
- 在测试环境演练。
- 检查锁表和回滚方案。
- 禁止手工直接修改生产表结构。

## 9. 备份

### 数据库

每日执行：

```bash
pg_dump -Fc xueji_zhice > /backup/db/xueji_zhice_$(date +%F).dump
```

### 文件

- 上传文件按日期目录增量备份。
- 正式运营迁移到私有 COS 并启用生命周期规则。
- 备份至少保存到与主服务器不同的位置。

保留策略：7 个日备份、4 个周备份、12 个学期/月度关键快照。

## 10. 监控

MVP 至少监控：

- 容器存活状态。
- CPU、内存、磁盘使用率。
- API P95、5xx 比例。
- PostgreSQL 连接数和慢查询。
- Redis 内存。
- OCR 任务积压和失败率。
- AI 调用成功率、耗时、Token 和主备切换。
- 磁盘与备份可恢复性。

## 11. 日志

- Nginx：访问和错误日志。
- Backend：JSON 结构化应用日志。
- Worker：任务 ID、资源 ID、耗时和错误码。
- 审计日志写数据库，不与普通日志混用。
- 日志轮转并限制保留期限。

禁止记录：密码、令牌、API Key、完整学生联系方式、完整原图和未经脱敏的 AI 输入。

## 12. 发布流程

```text
feature branch -> Pull Request -> CI -> review -> merge main -> deploy
```

CI 检查：

- Python 格式和单元测试。
- TypeScript 构建。
- Docker 镜像构建。
- 密钥扫描。
- 依赖漏洞基础扫描。

## 13. 故障降级

- AI 故障：规则报告和模板建议。
- OCR 故障：允许人工录入。
- Redis 故障：核心同步接口可继续运行，异步任务暂停。
- 文件服务故障：禁止新上传，已有学习功能继续。
- 数据库故障：系统进入只读或维护状态，严禁继续写入。

## 14. 上线检查表

- [ ] 仓库无真实密钥。
- [ ] 数据库和 Redis 未暴露公网。
- [ ] HTTPS 有效且可自动续期。
- [ ] 主备 AI 均通过脱敏测试。
- [ ] OCR 低置信度字段必须确认。
- [ ] 家庭数据隔离测试通过。
- [ ] 数据导出与删除有审计。
- [ ] 备份完成恢复演练。
- [ ] 整张试卷 OCR 路由不存在。
