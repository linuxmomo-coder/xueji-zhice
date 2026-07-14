# 学迹智评（Xueji Zhice）

面向学生与家长的 AI 综合学习评价与个性化学习干预系统。

## MVP 产品边界

- 角色：学生端、家长端、后台管理端；暂不建设教师端。
- OCR：只识别成绩、教师评语、学校评价、教材封面与目录；不识别整张试卷，不自动提取纸质错题。
- 学习闭环：学生评测、练习、错题、复测全部依靠本地题库。
- AI：用于评语结构化、学生版报告、家长版报告和学习计划建议。
- 家长确认：学生上传的成绩或评语必须经过家长确认后进入正式档案。

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLAlchemy + Pydantic
- 数据库：PostgreSQL + pgvector
- 缓存/队列：Redis
- OCR：PaddleOCR（本地部署）
- AI：阿里云百炼为主，腾讯混元为备用
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

## 本地启动（完成骨架后）

```bash
cp .env.example .env
docker compose -f deployment/docker-compose.yml up --build
```

启动后：

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
