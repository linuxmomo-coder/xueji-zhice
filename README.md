# 学迹智评（Xueji Zhice）v0.2.1

面向学生与家长的 AI 综合学习评价与个性化学习干预系统。

本版本在安全基线基础上，进一步修正角色登录和生产数据界面：

- 登录时选择家长、学生或管理员角色，后端校验账号角色一致；
- 登录后按真实角色进入独立功能空间，不再切换角色；
- 工作台统计、提示、科目和题量全部读取实际数据库；
- 无数据时显示真实空状态，不使用固定演示数字。

同时实现第一条可审计学习闭环：

```text
登录 → 学生档案 → 已审核题库 → 练习题快照 → 提交答案
→ 归一化判分 → 错题记录 → 原题复测
```

## 当前可用能力

- 家长注册；家长、学生、管理员按角色登录；刷新令牌轮换和退出。
- 学生、家长、管理员真实身份权限。
- 家庭成员和学生资源隔离。
- 学生档案创建与分页查询。
- 题目身份、版本、选项、作答字段和判分规则。
- 选择题、标准化文本、数值容差和数学表达式等价判分。
- 练习会话、题目快照、答题记录和错题状态。
- 成绩/评语等文件私有上传、摘要去重、家长确认和审计。
- React 角色化任务工作台，不展示原始 API JSON，不使用固化业务统计。
- PostgreSQL、Redis、Docker Compose、Nginx 和自动部署工作流。

## 工程边界

当前 OCR 和 AI 仍为适配器预留状态。生产环境不会加载演示接口，也不会自动写入演示数据。整张试卷拆题 OCR、纸质错题识别和高风险主观题自动评分不在当前范围。

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLAlchemy + Pydantic
- 数据库：PostgreSQL 16 + pgvector
- 迁移：Alembic
- 缓存/任务基础设施：Redis
- 文件：私有本地存储适配器，后续切换 MinIO/COS
- 部署：Docker Compose + Nginx + GitHub Actions

## 本地一键启动

```bash
cp .env.example .env
docker compose --env-file .env -f deployment/docker-compose.yml up --build
```

后端容器启动时自动执行：

```bash
alembic upgrade head
```

访问：

- Web：http://localhost
- 健康检查：http://localhost/health
- API 文档：http://localhost/docs

开发环境演示账号：

| 身份 | 邮箱 | 密码 |
|---|---|---|
| 家长 | parent@example.com | Parent123! |
| 学生 | student@example.com | Student123! |
| 管理员 | admin@example.com | Admin123! |

这些账号仅在 `APP_ENV=development`、`ENABLE_DEMO=true`、`SEED_DEMO_DATA=true` 时创建。生产环境使用这些配置会直接启动失败，且登录页不会展示演示账号。

## 后端开发

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

测试：

```bash
pytest -q
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 文档

0. [文档总索引](docs/00-DOCUMENT-INDEX.md)
1. [软件需求规格说明书](docs/01-SRS.md)
2. [概要设计说明书](docs/02-HLD.md)
3. [详细设计说明书](docs/03-LLD.md)
4. [数据库设计说明书](docs/04-DATABASE.md)
5. [AI 与 OCR 设计说明书](docs/05-AI-OCR-DESIGN.md)
6. [API 设计说明书](docs/06-API.md)
7. [部署与运维说明书](docs/07-DEPLOYMENT.md)
8. [题目勘误与相似题推荐](docs/08-FUTURE-QUESTION-QUALITY-AND-RECOMMENDATION.md)
9. [题库导入、媒体与答案归一化](docs/09-QUESTION-IMPORT-MEDIA-AND-ANSWER-NORMALIZATION.md)
10. [题库数据库结构 V2](docs/10-QUESTION-BANK-DATABASE-SCHEMA-V2.md)
11. [代码评审整改矩阵](docs/11-REVIEW-IMPLEMENTATION-MATRIX.md)
12. [测试与质量门禁](docs/12-TEST-PLAN.md)

## 生产安全要求

- 生产环境必须设置长度不少于 32 位的随机 `SECRET_KEY`。
- 禁止启用 demo、演示种子或自动建表。
- 禁止使用 SQLite 和通配 CORS。
- PostgreSQL、Redis 和上传目录不开放公网。
- `.env`、SSH 私钥和模型密钥不得进入 Git。
- 上线必须先备份、迁移、健康检查，再切换流量。

## v0.2.1 界面规则

- 角色只在登录页选择，登录成功后以后端返回角色为准。
- 家长、学生、管理员拥有各自独立导航。
- 首页数量、提示、科目和可选题量均来自当前数据库。
- 没有数据时显示“暂无数据”或功能不可用原因。
- 演示账号只允许开发环境使用，不在生产登录页展示。

## 评审基线

完整版本包在 `review/` 中保留本次代码评审原文，整改对应关系见 `docs/11-REVIEW-IMPLEMENTATION-MATRIX.md`。
