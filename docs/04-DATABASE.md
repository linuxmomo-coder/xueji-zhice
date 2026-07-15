# 学迹智评数据库设计说明书 v0.2

## 1. 数据库基线

- 生产：PostgreSQL 16+；开发/测试允许SQLite。
- 主键：UUID字符串；后续可迁移为原生PostgreSQL UUID。
- 时间：UTC `timestamptz`。
- 可变结构：JSON/JSONB；身份、权限、状态、金额和关键检索字段必须结构化。
- 迁移：Alembic；生产应用不得使用 `create_all` 代替迁移。
- 隔离：家庭业务表必须带 `family_id` 或能通过外键确定家庭范围。

## 2. 当前迁移

`0001_v020_security_learning_loop` 创建 v0.2 基线。部署入口执行：

```bash
alembic upgrade head
```

回滚仅用于演练或未承载真实数据的环境。生产回滚优先使用向前修复迁移和备份恢复。

## 3. 身份与家庭

### users

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | varchar(36) PK | 用户ID |
| email | varchar(254) unique | 登录邮箱 |
| password_hash | varchar(255) | PBKDF2-SHA256哈希 |
| display_name | varchar(80) | 显示名称 |
| role | varchar(20) | parent/student/admin |
| status | varchar(20) | active/locked/deleted |
| last_login_at | timestamptz nullable | 最近登录 |
| created_at/updated_at | timestamptz | 审计时间 |

### families

`id, name, status, primary_guardian_user_id, created_at, updated_at`。

### family_members

| 字段 | 说明 |
|---|---|
| family_id/user_id | 联合唯一 |
| relation_type | guardian/student/member |
| is_primary_guardian | 主监护人标记 |
| permissions | 扩展权限JSON |
| status | active/revoked |

### user_sessions

保存刷新会话，不保存明文刷新令牌：`user_id, token_jti, token_hash, expires_at, revoked_at, user_agent, ip_hash`。

## 4. 学生档案

### students

| 字段 | 说明 |
|---|---|
| id | 学生档案ID |
| family_id | 强制家庭范围索引 |
| user_id | 学生登录账号，可空 |
| nickname/birth_date/region | 基础资料 |
| school_system/current_grade/current_term | 学制与当前学期 |
| daily_minutes_limit | 每日学习限制 |
| profile_status/deleted_at | 生命周期与软删除 |
| created_by_user_id | 创建人 |

约束：学生账号至多关联一个学生档案；跨家庭查询必须在应用层拒绝。

## 5. 生产级题库当前落地结构

### questions

保存稳定身份和生命周期：`question_code, subject, grade, lifecycle_status, current_version_id, suspended_reason`。

### question_versions

保存不可静默覆盖的内容版本：

- `question_id + version_no`联合唯一；
- `display_type, stem_content, explanation_content`；
- `difficulty, cognitive_level, estimated_seconds, total_score`；
- `scoring_mode, common_errors, content_checksum`；
- `review_status, publication_status, reviewed_by_user_id, published_at`。

### question_options

`question_version_id, option_key, content, sort_order, is_fixed_position, metadata`。

### question_response_fields

一题可多个作答区：`field_key, field_type, prompt, required, score_weight, input_config`。

### question_answer_rules

| 字段 | 说明 |
|---|---|
| rule_type | choice_set/exact_text/normalized_text/numeric_tolerance/symbolic_equivalence/set_equivalence/manual |
| accepted_values | 标准值集合JSON |
| normalization_profile | text_zh_v1/math_zh_v1等 |
| case_sensitive/order_sensitive | 大小写与顺序规则 |
| allow_fullwidth_equivalent | 全角半角等价 |
| allow_fraction_decimal_equivalent | 分数小数等价 |
| unit/unit_required | 单位规则 |
| absolute_tolerance/relative_tolerance | 数值误差 |
| parser_profile/parse_failure_action | 安全解析配置 |
| rule_version | 判分器规则版本 |

### question_assets / question_version_assets

媒体二进制进入私有存储；数据库保存provider、object_key、MIME、大小、SHA-256、尺寸、来源和版本角色。禁止把临时签名URL作为稳定字段。

## 6. 学习闭环

### practice_sessions

`student_id, family_id, practice_type, subject, status, started_at, finished_at, total_count, answered_count, correct_count, score_summary`。

### practice_items

- `session_id, question_id, question_version_id, sequence_no`；
- `question_snapshot`保存当时题干、选项和必要显示数据；
- `status`保证一次有效提交不能被静默覆盖。

### attempts

- `answer_raw`：学生原始输入；
- `answer_normalized`：归一化结果；
- `evaluation_detail`：规则、解析和各字段结果；
- `is_correct, score, duration_seconds, hint_count, submitted_at`。

### wrong_questions

`student_id + question_id`联合唯一；保存首次/最近错误、错误次数、状态、最新attempt和下次复习时间。

## 7. 资料与审计

### learning_documents

`family_id, student_id, uploaded_by_user_id, document_type, file_name, storage_provider, object_key, file_sha256, mime_type, size_bytes, status, structured_data, confirmed_data, confirmed_by_user_id, confirmed_at`。

### audit_events

`actor_user_id, family_id, action, resource_type, resource_id, before_data, after_data, request_id, ip_hash, created_at`。

当前记录学生创建、资料上传与确认；题目发布、权限、导出删除和模型配置将在后续补齐。

## 8. 关键索引

- `users(email)`唯一；
- `family_members(family_id,user_id)`唯一；
- `students(family_id,created_at)`；
- `questions(question_code)`唯一；
- `questions(subject,grade,lifecycle_status)`；
- `question_versions(question_id,version_no)`唯一；
- `practice_sessions(student_id,created_at)`；
- `attempts(student_id,submitted_at)`；
- `wrong_questions(student_id,state,next_review_at)`；
- `learning_documents(student_id,file_sha256)`用于重复检查。

## 9. 下一阶段数据库

教材目录、知识点映射、题型分类、Excel导入批次、题目审核细分、质量指标、相似题关系、勘误和历史重判按docs/08—10实施，不在本迁移中伪装为已完成。
