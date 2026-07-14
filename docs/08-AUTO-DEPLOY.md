# 自动部署操作手册

## 目标

本仓库使用 GitHub Actions 将 `main` 分支部署到腾讯云 Ubuntu 服务器。部署采用 SSH 连接服务器，在服务器上拉取代码并执行 Docker Compose。

当前自动部署不会自动购买云资源、申请域名、配置实名认证或创建密钥；这些步骤必须由项目负责人完成。

## 一次性由负责人完成

### 1. 腾讯云

创建一台 Ubuntu 22.04/24.04 服务器，建议：

- 4 核 8 GB 内存
- 100 GB 系统盘
- 公网 IPv4
- 腾讯云安全组只开放 TCP 22、80、443

不要开放 5432、6379 或其他容器内部端口。

### 2. 服务器初始化

在本地准备好 SSH 私钥后，登录服务器执行：

```bash
sudo bash -c 'curl -fsSL https://raw.githubusercontent.com/linuxmomo-coder/xueji-zhice/main/scripts/bootstrap-ubuntu.sh | bash'
```

更安全的方式是先审阅脚本，再复制到服务器执行。脚本会安装 Docker、Docker Compose、Git 和 UFW，并创建 `/opt/xueji-zhice`。

之后编辑：

```bash
sudo nano /opt/xueji-zhice/.env
```

必须修改：

- `APP_ENV=production`
- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `DATABASE_URL` 中的数据库密码
- `CORS_ORIGINS`
- AI/OCR供应商密钥（尚未接入时可保留 mock）

启动前检查：

```bash
cd /opt/xueji-zhice
docker compose -f deployment/docker-compose.yml config
docker compose -f deployment/docker-compose.yml up -d --build
curl --fail http://127.0.0.1/health
```

### 3. GitHub Actions Secrets

在仓库进入 **Settings -> Environments -> New environment**，创建环境：

```production```

建议开启部署审批。然后在该环境的 **Secrets** 中添加：

| Secret | 值 |
|---|---|
| `DEPLOY_HOST` | 腾讯云公网IP |
| `DEPLOY_USER` | 服务器登录用户，例如 `ubuntu` |
| `DEPLOY_SSH_KEY` | 对应私钥完整内容 |
| `DEPLOY_PATH` | `/opt/xueji-zhice` |
| `DEPLOY_PORT` | 可选，默认 `22` |

不要把私钥、密码或 API Key 提交到仓库。

## 发布流程

1. 将代码合并到 `main`。
2. GitHub Actions 自动触发 `Deploy production`。
3. 若配置了审批，先由负责人批准。
4. Actions 通过 SSH 在服务器执行：
   - 拉取 `main`
   - 校验 Compose 配置
   - 构建并重启容器
   - 检查 `/health`
5. 健康检查失败时工作流失败，保留服务器现场供排查。

## 域名和 HTTPS

当前配置先支持 IP + HTTP 内测。正式开放前还需要：

1. 购买并实名认证域名。
2. 将 A 记录解析到服务器公网 IP。
3. 按所在地要求完成备案。
4. 修改 Nginx 的 `server_name`。
5. 配置 HTTPS 证书并强制跳转 HTTPS。

## 当前发布边界

- 当前仍是 MVP 演示工程，默认 OCR/AI 为 mock。
- 真实用户上线前必须补齐真实认证、家庭数据隔离、数据库迁移、备份恢复和隐私协议。
- 本流程不开放整张试卷 OCR 和纸质错题自动提取。
