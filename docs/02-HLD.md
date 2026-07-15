# 学迹智评概要设计说明书（HLD）v0.2

## 1. 架构目标

采用“模块化单体 + 异步任务预留 + 可替换适配器”。当前规模不拆微服务，先建立清晰模块边界、事务一致性和可测试性。

## 2. 总体结构

```text
React Web
   ↓ HTTPS / Nginx
FastAPI API/BFF
   ├─ identity          认证、会话、家庭权限
   ├─ student_profile   学生档案和家庭关系
   ├─ question_bank     题目、版本、答案规则、媒体
   ├─ practice          组题、快照、答题、错题
   ├─ evidence          资料上传、确认和审计
   ├─ insight           规则指标、AI报告预留
   └─ platform_admin    题库审核和平台配置预留
        ↓
PostgreSQL / pgvector
Redis
Private Storage Adapter
OCR / LLM Adapters
```

## 3. 运行边界

### 3.1 身份边界

- 后端签发角色和家庭上下文。
- 前端只展示当前身份，不决定权限。
- 所有学生资源访问经过统一依赖校验。
- 管理员权限与家庭成员关系分开。

### 3.2 数据边界

- 家庭表是家长数据隔离边界。
- 学生账号通过 `students.user_id` 限定本人数据。
- 题库属于平台主数据，不属于家庭。
- 资料和练习冗余保存 `family_id` 便于索引和审计。

### 3.3 Demo 边界

```text
APP_ENV=development/test
AND ENABLE_DEMO=true
AND SEED_DEMO_DATA=true
```

只有同时满足时才加载演示路由和演示种子。production 环境直接拒绝。

## 4. 模块职责

| 模块 | 职责 | 当前实现 |
|---|---|---|
| identity | 注册、登录、刷新、退出、权限 | 已实现 |
| student_profile | 学生建档、分页、家庭隔离 | 已实现 |
| question_bank | 题目版本、选项、作答字段、规则 | 已实现基础结构 |
| practice | 组题、题目快照、判题、错题 | 已实现首条闭环 |
| evidence | 私有上传、摘要去重、确认、审计 | 已实现人工确认基线 |
| insight | 指标、报告、推荐 | 规则工作台已实现；AI待接入 |
| platform_admin | 题库审核、配置、任务监控 | 结构预留 |

## 5. 关键数据流

### 5.1 认证

```text
注册/登录
→ 密码哈希校验
→ 查询家庭成员关系
→ 签发 access + refresh
→ refresh摘要入库
→ 刷新时撤销旧refresh并签发新令牌
```

### 5.2 练习

```text
选择学生和科目
→ 权限校验
→ 查询 active 题目和 approved/published 版本
→ 创建 PracticeSession
→ 写入 PracticeItem + 题目快照
→ 学生提交答案
→ 规则归一化和判分
→ 写 Attempt
→ 更新 WrongQuestion
→ 完成会话
```

### 5.3 文件

```text
上传文件
→ MIME/大小校验
→ SHA-256
→ 检测重复
→ 保存私有对象
→ LearningDocument awaiting_confirmation
→ 家长确认
→ AuditEvent
```

## 6. 数据库迁移

- 应用生产启动不调用 `Base.metadata.create_all`。
- 容器入口先执行 `alembic upgrade head`。
- 当前初始迁移创建 v0.2 基线表。
- 后续版本使用显式迁移脚本，不覆盖已发布题目和历史答题快照。

## 7. 存储架构

当前 `LocalPrivateStorage` 将文件保存在私有卷，业务层只依赖统一接口。

后续实现：

- `MinIOStorage`：开发/私有部署；
- `COSStorage`：腾讯云生产；
- 数据库只保存 provider、object_key、摘要和元数据；
- 前端通过后端短期签名地址访问。

## 8. 安全控制

- PBKDF2-SHA256密码哈希。
- JWT短期访问令牌。
- 可撤销刷新令牌摘要。
- CORS明确域名。
- Nginx限流和安全响应头。
- 生产配置 fail-fast。
- 统一错误信息隐藏内部堆栈。
- request_id贯穿响应和审计。

## 9. 可扩展路径

优先扩展顺序：

1. MinIO/COS存储适配器；
2. 异步任务与OCR；
3. 题库Excel导入和审核；
4. 教材/知识点/题型分类；
5. 同类题、变式题和间隔复习；
6. AI报告适配器；
7. 高并发时再拆Worker或题库检索服务。
