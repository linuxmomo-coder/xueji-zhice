# 学迹智评 API 设计说明书 v0.2

## 1. 协议

- Base URL：`/api/v1`
- 认证：`Authorization: Bearer <access_token>`
- 时间：ISO 8601 UTC
- 分页：`page`、`page_size`，最大100
- 请求追踪：响应头 `X-Request-ID`

成功：

```json
{"data": {}, "meta": {"request_id": "..."}}
```

失败：

```json
{"error":{"code":"FAMILY_001","message":"无权访问该学生数据","request_id":"...","details":{}}}
```

## 2. 当前可用接口（available）

### 认证

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/auth/register/parent` | public | 创建家长、家庭和主监护关系 |
| POST | `/auth/login` | public | 登录并返回access/refresh |
| POST | `/auth/refresh` | refresh | 轮换刷新令牌 |
| POST | `/auth/logout` | refresh | 撤销会话 |
| GET | `/auth/me` | login | 当前用户和家庭摘要 |

### 学生

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/students?page=&page_size=` | 本人或家庭范围分页 |
| POST | `/students` | 家长/管理员创建学生 |
| GET | `/students/{student_id}` | 统一学生范围校验 |

### 题库

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/questions` | 管理员查看已发布题目；支持科目/年级分页 |

学生练习接口只返回题目快照，不返回标准答案。

### 练习

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/practice-sessions` | 创建会话和题目快照 |
| GET | `/practice-sessions/{id}` | 会话摘要 |
| GET | `/practice-sessions/{id}/next` | 下一题 |
| POST | `/practice-sessions/{id}/answers` | 提交、归一化、判分、错题更新 |
| GET | `/students/{id}/wrong-questions` | 错题列表 |

### 资料

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/documents/upload` | 私有上传、MIME/大小/摘要/重复校验 |
| GET | `/students/{id}/documents` | 家庭范围资料列表 |
| POST | `/documents/{id}/confirm` | 仅家长/管理员确认，保存审计 |

### 工作台

`GET /dashboard`根据服务器确认的角色返回允许的数据和行动，不接受role参数。

### Demo

`/demo/*`只有在非生产环境且显式`ENABLE_DEMO=true`时存在；生产OpenAPI中不得出现。

## 3. 计划接口（planned）

- 题库Excel导入、审核、发布和版本修订；
- 教材目录、知识点和题型分类；
- OCR异步任务状态；
- 报告生成与历史；
- 同类题/变式题复测；
- 勘误、AI复核和历史重判；
- 数据导出、删除和通知。

## 4. 错误码

| 错误码 | 含义 |
|---|---|
| AUTH_001 | 未认证或令牌无效 |
| AUTH_002 | 角色权限不足 |
| AUTH_003 | 登录凭据错误 |
| FAMILY_001 | 跨家庭或非本人资源 |
| DOC_001 | 文件类型/大小不支持 |
| DOC_002 | 文档状态不允许操作 |
| BANK_001 | 没有可发布/可练习题目 |
| PRACTICE_001 | 会话或题目状态不允许 |
| PRACTICE_002 | 重复提交 |
| VALIDATION_001 | 请求参数错误 |
| SYSTEM_001 | 服务内部错误 |

## 5. 契约治理

- OpenAPI是当前可用接口事实来源；
- 文档不得把planned写成available；
- 前端类型后续从OpenAPI生成；
- 请求/响应破坏性变更必须增加API版本或兼容期。
