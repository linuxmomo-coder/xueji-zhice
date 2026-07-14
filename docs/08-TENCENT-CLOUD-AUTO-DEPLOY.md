# 腾讯云自动部署快速说明

## 目标

合并代码到 `main` 后，GitHub Actions 通过 SSH 登录腾讯云服务器，更新代码、重建 Docker 服务并执行健康检查。

## 你需要先完成的事项

### 1. 创建腾讯云轻量应用服务器

建议：

- Ubuntu 22.04/24.04 LTS
- 4 核 8 GB（MVP 最低 2 核 4 GB）
- 系统盘 80 GB 以上
- 腾讯云防火墙只开放 TCP 22、80、443
- 不开放 5432、6379

### 2. 首次初始化服务器

SSH 登录服务器后执行：

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
sudo mkdir -p /opt/xueji-zhice
sudo chown -R "$USER":"$USER" /opt/xueji-zhice
git clone https://github.com/linuxmomo-coder/xueji-zhice.git /opt/xueji-zhice
cd /opt/xueji-zhice
cp .env.example .env
nano .env
```

至少修改：

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `CORS_ORIGINS`
- 真实 AI 密钥暂时可留空，默认使用 mock 适配器

然后首次启动：

```bash
docker compose -f deployment/docker-compose.yml up -d --build
curl --fail http://127.0.0.1/health
```

### 3. GitHub 仓库配置 Secrets

进入：

`Settings -> Environments -> New environment -> production`

为 `production` 添加：

| Secret | 内容 |
|---|---|
| `SERVER_HOST` | 腾讯云公网 IP 或域名 |
| `SERVER_USER` | SSH 用户名，例如 `ubuntu` |
| `SERVER_SSH_KEY` | 对应服务器用户的 SSH 私钥全文 |
| `SERVER_PORT` | SSH 端口，通常为 `22` |
| `DEPLOY_PATH` | `/opt/xueji-zhice` |

私钥只保存到 GitHub Secret，不要提交到仓库或发送到聊天中。

建议给 `production` 设置 Required reviewers，这样合并到 `main` 后需你批准才部署。

## 发布流程

```text
功能分支
  -> Pull Request
  -> CI 通过
  -> 合并 main
  -> production 审批
  -> SSH 部署
  -> 健康检查
```

也可以在 GitHub Actions 页面手动运行 `Deploy to Tencent Cloud`。

## 当前限制

- 首次服务器初始化仍需人工完成。
- 当前 Compose 在服务器上构建镜像，首次部署较慢。
- 数据库迁移尚未纳入自动流程，正式迁移前必须先备份。
- HTTPS 和域名配置需在服务器上线后另行完成。
- 不要把真实学生数据用于首次部署测试。
