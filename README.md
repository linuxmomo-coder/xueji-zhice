# 学迹智评（Xueji Zhice）v0.3.0

面向学生与家长的学习证据管理、题库练习、错题复测、OCR资料确认和证据化AI学习报告系统。

## v0.3.0定位

这是首个生产候选版本。正式界面不使用固定统计、演示评价或前端角色切换；身份、数据和功能均以后端权限及实际数据库为准。

核心闭环：

```text
家长注册与授权
→ 创建学生档案并绑定学生账号
→ 管理员导入、审核和发布题库
→ 学生按实际年级完成练习
→ 规则判分、错题和原题复测
→ 上传成绩或评语资料
→ OCR识别、家长校对确认
→ 生成引用真实证据的AI学习报告
→ 题目勘误、修正版和历史重判
```

## 当前可用能力

- 家长注册、邮箱验证、密码找回、修改密码和刷新会话轮换；
- 家长、学生、管理员按角色登录，后端验证角色一致；
- 家庭成员、学生账号和学生档案隔离；
- 监护人授权、数据导出、账号停用和审计事件；
- Excel题库导入、逐行校验、错误隔离、来源版权、审核和发布；
- 题目身份、版本、选项、作答字段、判分规则和题图资产；
- 按实际年级和科目组题；
- 选择题、文本、数值容差、分数及基础数学表达式等价判分；
- 练习快照、答题记录、错题、复测状态；
- 私有资料上传、OCR异步任务、家长修改和确认；
- 百炼主模型、混元备用模型的证据化AI报告；
- 题目勘误、管理员复核、修正版、历史重判、通知和题型推荐；
- PostgreSQL、Redis、S3/COS兼容对象存储；
- OCR、AI和历史重判三个独立Worker；
- Alembic显式迁移、CI、Docker Compose、部署预检、备份和冒烟测试。

## 首发范围之外

v0.3.0不提供以下能力，界面和销售材料不得描述为已实现：

- 整张试卷自动拆题；
- 手写作业答案识别和纸质错题自动提取；
- 高风险主观题自动评分；
- 教师端、班级管理和学生公开排名；
- 完整教材知识图谱、向量相似检索；
- 多级管理员RBAC。

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：FastAPI、SQLAlchemy、Pydantic
- 数据库：PostgreSQL 16、pgvector
- 迁移：Alembic
- 队列：Redis
- 文件：S3兼容存储或腾讯云COS
- OCR：PaddleOCR HTTP适配器
- AI：阿里云百炼主模型、腾讯混元备用模型
- 部署：Docker Compose、Nginx、GitHub Actions

## 本地开发

```bash
cp .env.example .env
docker compose --env-file .env -f deployment/docker-compose.yml up --build
```

访问：

- Web：http://localhost
- 健康检查：http://localhost/health
- 开发环境API文档：http://localhost/docs

开发环境演示账号只在以下配置同时成立时创建：

```text
APP_ENV=development
ENABLE_DEMO=true
SEED_DEMO_DATA=true
```

生产环境启用以上配置会直接启动失败。

## 生产部署

1. 根据 `deployment/.env.production.example` 创建根目录 `.env`；
2. 配置PostgreSQL、Redis、COS/S3、SMTP、OCR和AI密钥；
3. 公网入口必须使用HTTPS，由可信反向代理或云负载均衡终止TLS；
4. 执行生产预检：

```bash
sh deployment/preflight.sh
```

5. 执行部署：

```bash
APP_DIR=/opt/xueji-zhice sh deployment/deploy.sh
```

6. 切换流量前执行冒烟测试：

```bash
BASE_URL=https://your-domain.example sh deployment/smoke-test.sh
```

数据库恢复必须经过人工确认：

```bash
CONFIRM_RESTORE=YES_RESTORE_XUEJI \
  sh deployment/restore-postgres.sh /absolute/path/postgres_backup.sql
```

## 生产安全要求

- `SECRET_KEY`不少于32位随机值；
- 禁止生产SQLite、Demo、演示种子、自动建表和API文档；
- CORS必须填写明确域名；
- PostgreSQL和Redis不得暴露公网；
- 学生资料和题图使用私有对象存储；
- `.env`、SSH私钥、SMTP密码、OCR令牌和模型Key不得提交到Git；
- 未通过CI、生产预检和HTTPS冒烟测试不得切换流量。

## 文档

- `docs/01-SRS.md`：需求规格说明书
- `docs/02-HLD.md`：概要设计
- `docs/03-LLD.md`：详细设计
- `docs/04-DATABASE.md`：数据库设计
- `docs/05-AI-OCR-DESIGN.md`：AI与OCR设计
- `docs/06-API.md`：API说明
- `docs/07-DEPLOYMENT.md`：部署运维
- `docs/08-FUTURE-QUESTION-QUALITY-AND-RECOMMENDATION.md`：题目质量与推荐
- `docs/09-QUESTION-IMPORT-MEDIA-AND-ANSWER-NORMALIZATION.md`：题库导入与判分
- `docs/10-QUESTION-BANK-DATABASE-SCHEMA-V2.md`：题库数据库目标结构
- `docs/12-TEST-PLAN.md`：测试与质量门禁
- `RELEASE_NOTES.md`：v0.3.0发布边界
