# 学迹智评详细设计说明书（LLD）v0.2

## 1. 代码结构

```text
backend/app/
├── api/              # HTTP路由和响应转换
├── core/             # 配置、安全、错误、request_id
├── db/               # SQLAlchemy会话
├── repositories/     # 用户、学生、题库查询
├── services/         # 认证、判分、练习、存储、审计
├── dependencies.py   # current_user、角色和学生范围校验
├── models.py         # v0.2数据模型
├── schemas.py        # 请求/响应Schema
├── seed.py           # 仅开发环境演示数据
└── main.py
```

## 2. 配置启动设计

`Settings.validate_runtime()` 在应用 lifespan 进入时执行。

生产检查：

- `SECRET_KEY` 长度不少于32且不是默认值；
- `ENABLE_DEMO=false`；
- `SEED_DEMO_DATA=false`；
- `AUTO_CREATE_SCHEMA=false`；
- `DATABASE_URL` 不是 SQLite；
- `CORS_ORIGINS` 不为空且没有 `*`；
- 数据库密码不是已知弱默认值。

任一条件不满足时抛出 RuntimeError，阻止服务上线。

## 3. 密码和令牌

### 3.1 密码

```text
pbkdf2_sha256$iterations$salt$digest
```

- 随机16字节盐；
- 390,000次PBKDF2-SHA256；
- 使用 `hmac.compare_digest` 比较。

### 3.2 访问令牌

载荷：

```json
{
  "sub": "user_id",
  "role": "parent",
  "family_id": "family_id",
  "type": "access",
  "jti": "uuid",
  "iat": "...",
  "exp": "..."
}
```

### 3.3 刷新令牌

- JWT本体只发给客户端；
- 数据库保存 SHA-256 摘要和 jti；
- 每次刷新撤销旧会话并创建新会话；
- 退出只撤销对应 refresh 会话。

## 4. 权限依赖

- `get_current_user`：校验 access token 和用户状态；
- `require_roles`：限制 parent/student/admin；
- `current_family_id`：读取用户首要家庭；
- `get_accessible_student`：管理员可访问，学生仅本人，家长仅本家庭。

路由不得自行信任 `role`、`family_id` 或前端状态。

## 5. 题库对象

### 5.1 Question

稳定身份和生命周期；不保存易修改内容。

### 5.2 QuestionVersion

保存题干、解析、难度、认知层级、总分、审核和发布状态。

### 5.3 QuestionResponseField

一题多个作答区域：`answer`、`blank_1`、`blank_2`、`reason`。

### 5.4 QuestionAnswerRule

判分规则类型：

- `choice_set`
- `exact_text`
- `normalized_text`
- `numeric_tolerance`
- `symbolic_equivalence`
- `set_equivalence`
- `manual`

## 6. 安全数学解析

流程：

1. Unicode NFKC；
2. 统一乘号、除号、负号、幂、圆周率和根号；
3. `ast.parse(..., mode="eval")` 只生成语法树；
4. 自定义遍历器只接受数字、变量、加减乘除、幂、一元正负、sqrt和abs；
5. 转换为 SymPy 表达式；
6. 两表达式差值化简为0则等价。

代码不调用 Python `eval`，不允许属性访问、下标、列表、字典、导入或任意函数。

## 7. 练习事务

### create_session

- 校验学生访问权；
- 查询符合科目的 active 题目；
- 只使用 approved/published 版本；
- 创建 session；
- 每题生成 PracticeItem 和快照；
- 提交事务。

### submit_answer

- 校验会话和 item 状态；
- 加载版本、作答字段和规则；
- 归一化与判分；
- 创建 Attempt；
- 更新 item 和 session；
- 创建或更新 WrongQuestion；
- 最后一题完成后关闭会话；
- 单事务提交。

## 8. 文件上传

- 读取不超过 `MAX_UPLOAD_MB + 1`；
- MIME白名单；
- 计算SHA-256；
- 对同学生和摘要去重；
- 对象键使用 `family_id/student_id/sha256.ext`；
- 文件名仅保留安全的 basename；
- 私有目录不由Nginx直接暴露。

## 9. 错误协议

业务异常使用 `ApiError(status_code, code, message, details)`。

- 认证失败：AUTH_*；
- 家庭越权：FAMILY_001；
- 文档状态：DOC_*；
- 题库：BANK_*；
- 练习：PRACTICE_*；
- 未捕获异常对用户统一返回 SYSTEM_001。

## 10. 审计

当前写入：

- 学生创建；
- 资料上传；
- 资料确认。

后续必须补充：题目发布/下架、答案变更、数据导出/删除、权限变更、模型配置修改和历史重判。

## 11. 前端交互

- 未登录显示登录/家长注册页；
- 登录后显示真实身份，不提供角色切换按钮；
- 导航按首页、学生档案、练习与错题、资料上传、题库管理组织；
- API错误映射为中文行动提示；
- 操作结果使用任务卡和反馈，不显示原始JSON；
- 数学填空提示支持根号和全角输入。
