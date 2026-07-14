# 学迹智评（Xueji Zhice）

面向学生与家长的 AI 综合学习评价与个性化学习干预系统。

## MVP 产品边界

- 角色：学生端、家长端、后台管理端；暂不建设教师端。
- OCR：只识别成绩、教师评语、学校评价、教材封面与目录；不识别整张试卷，不自动提取纸质错题。
- 学习闭环：学生评测、练习、错题、复测全部依靠本地题库。
- AI：用于评语结构化、学生版报告、家长版报告和学习计划建议。
- 家长确认：学生上传的成绩或评语必须经过家长确认后进入正式档案。

## 当前工程能力

- 三角色 React 工作台。
- FastAPI 与 OpenAPI 文档。
- PostgreSQL/pgvector 数据模型骨架。
- Redis 与 Docker Compose 部署。
- 学生、教材和本地题库演示种子数据。
- 成绩/评语 OCR 候选结果演示接口。
- 本地题库专项练习接口。
- 学生版和家长版 AI 结构化报告演示接口。
- GitHub Actions：后端测试、前端构建、Docker 构建检查。

真实 PaddleOCR、阿里云百炼和腾讯混元均通过环境变量预留，默认使用模拟适配器，确保没有密钥时也能启动工程。

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLAlchemy + Pydantic
- 数据库：PostgreSQL + pgvector
- 缓存/队列：Redis
- OCR：PaddleOCR（本地部署，下一阶段接入）
- AI：阿里云百炼为主，腾讯混元为备用（下一阶段接入）
- 部署：Docker Compose + Nginx，目标环境为腾讯云 Ubuntu

## 仓库结构

```text
.
├── docs/                 # 需求与设计文档
├── frontend/             # 学生/家长/后台 Web 前端
├── backend/              # FastAPI 后端
├── deployment/           # Docker 与部署配置
├── .env.example          # 环境变量示例
└── README.md
```

## 设计文档

1. [软件需求规格说明书](docs/01-SRS.md)
2. [概要设计说明书](docs/02-HLD.md)
3. [详细设计说明书](docs/03-LLD.md)
4. [数据库设计说明书](docs/04-DATABASE.md)
5. [AI 与 OCR 设计说明书](docs/05-AI-OCR-DESIGN.md)
6. [API 设计说明书](docs/06-API.md)
7. [部署与运维说明书](docs/07-DEPLOYMENT.md)
8. [后续升级：题目勘误与相似题型推荐](docs/08-FUTURE-QUESTION-QUALITY-AND-RECOMMENDATION.md)
9. [题库导入、媒体存储与答案归一化](docs/09-QUESTION-IMPORT-MEDIA-AND-ANSWER-NORMALIZATION.md)
10. [题库数据库结构 V2](docs/10-QUESTION-BANK-DATABASE-SCHEMA-V2.md)

## Docker 一键启动

```bash
cp .env.example .env
# 修改 .env 中的 SECRET_KEY 与 POSTGRES_PASSWORD
docker compose -f deployment/docker-compose.yml up --build
```

启动后：

- Web 工作台：http://localhost
- 后端健康检查：http://localhost/health
- API 文档：http://localhost/docs
- OpenAPI：http://localhost/openapi.json

## 分开开发

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

## 演示接口

- `GET /api/v1/dashboard/student`
- `GET /api/v1/dashboard/parent`
- `GET /api/v1/dashboard/admin`
- `GET /api/v1/students`
- `GET /api/v1/textbooks`
- `GET /api/v1/questions`
- `POST /api/v1/documents/demo-ocr`
- `POST /api/v1/practice-sessions/demo`
- `POST /api/v1/reports/demo`

## 安全要求

- 不要提交 `.env`、API Key、服务器密码或私钥。
- PostgreSQL 和 Redis 不开放公网端口。
- 正式学生数据不得用于演示或公共模型训练。
- 学生上传的成绩与评语必须由家长确认后进入正式档案。
