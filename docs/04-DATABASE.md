# 学迹智评数据库设计说明书

## 1. 数据库技术

- PostgreSQL 16+
- pgvector 扩展用于题目、知识点和评语语义检索
- UUID 主键
- UTC 时间存储，前端按用户时区展示
- JSONB 只保存结构不稳定的数据，关键业务字段必须结构化
- 所有正式业务表包含 `created_at`、`updated_at`，重要表包含软删除或版本字段

## 2. 数据域

1. 身份与家庭
2. 学生档案与学期
3. 教材、目录和知识点
4. 上传资料、OCR、成绩和评语
5. 本地题库与版权审核
6. 练习、答题、错题和掌握度
7. 任务、奖励和学习行为
8. AI 报告、异步任务与审计

## 3. 核心表

### 3.1 users

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | 用户 ID |
| email | varchar unique nullable | 邮箱 |
| phone | varchar unique nullable | 手机号 |
| password_hash | varchar | 密码哈希 |
| role | varchar | parent/student/admin |
| status | varchar | active/locked/deleted |
| display_name | varchar | 显示名 |
| last_login_at | timestamptz | 最后登录 |

至少 email/phone 之一非空。

### 3.2 families

- `id`
- `name`
- `primary_guardian_user_id`
- `status`

### 3.3 family_members

- `family_id`
- `user_id`
- `relation_type`
- `is_primary_guardian`
- `permissions JSONB`

唯一约束：`(family_id, user_id)`。

### 3.4 students

- `id`
- `family_id`
- `user_id nullable`
- `nickname`
- `birth_date`
- `region_code`
- `school_name nullable`
- `school_system`：6-3、5-4 等
- `enrollment_year`
- `current_grade`
- `daily_minutes_limit`
- `profile_status`

### 3.5 academic_terms

- `id`
- `name`，如 2026-2027 第一学期
- `school_year_start`
- `school_year_end`
- `term_no`
- `start_date`
- `end_date`

### 3.6 student_term_profiles

保存每学期快照：

- `student_id`
- `term_id`
- `administrative_grade`
- `school_system`
- `status`
- `archived_at`

唯一约束：`(student_id, term_id)`。

### 3.7 subjects 与 student_subject_levels

`subjects` 保存数学、语文、英语等主数据。

`student_subject_levels`：

- `student_id`
- `term_id`
- `subject_id`
- `level_grade`
- `confidence`
- `source`

## 4. 教材与知识体系

### 4.1 textbooks

- `id`
- `subject_id`
- `publisher`
- `version_name`
- `revision_year`
- `curriculum_standard_version`
- `grade`
- `volume`
- `isbn nullable`
- `status`

唯一索引：出版社、版本、修订年份、科目、年级、册次。

### 4.2 curriculum_nodes

统一保存单元、章节、课时和知识点：

- `id`
- `textbook_id`
- `parent_id nullable`
- `node_type`：unit/chapter/lesson/knowledge_point
- `code`
- `name`
- `sort_order`
- `standard_code nullable`
- `metadata JSONB`

### 4.3 knowledge_point_relations

- `from_knowledge_point_id`
- `to_knowledge_point_id`
- `relation_type`：prerequisite/next/related/confusable

### 4.4 student_textbooks

- `student_id`
- `term_id`
- `subject_id`
- `textbook_id`
- `current_node_id nullable`
- `progress_source`
- `confirmed_by_user_id`
- `confirmed_at`
- `is_active`

同学生、学期、科目仅一条 active。

## 5. OCR 与学校资料

### 5.1 learning_documents

- `id`
- `family_id`
- `student_id`
- `uploaded_by_user_id`
- `document_type`：score/comment/evaluation/textbook_cover/textbook_catalog/progress
- `file_key`
- `file_sha256`
- `mime_type`
- `status`
- `ocr_confidence`
- `ocr_raw_text`
- `structured_data JSONB`
- `confirmed_data JSONB`
- `confirmed_by_user_id`
- `confirmed_at`
- `rejection_reason`

索引：`student_id, created_at`；唯一去重索引可结合 `student_id, file_sha256`。

### 5.2 document_revisions

保存确认前后的字段差异、操作者和时间。

### 5.3 scores

- `student_id`
- `term_id`
- `subject_id`
- `document_id nullable`
- `exam_name`
- `exam_type`
- `exam_date`
- `raw_score numeric nullable`
- `full_score numeric nullable`
- `grade_value varchar nullable`
- `class_average nullable`
- `class_rank nullable`
- `grade_rank nullable`
- `scope_text`
- `is_confirmed`

### 5.4 teacher_comments 与 comment_labels

`teacher_comments` 保存原文、日期、来源文档。

`comment_labels` 保存：

- `dimension`
- `level`
- `evidence_text`
- `confidence`
- `is_confirmed`

## 6. 题库

### 6.1 questions

- `id`
- `question_code unique`
- `subject_id`
- `question_type`
- `stem JSONB`
- `options JSONB`
- `answer JSONB`
- `explanation JSONB`
- `hints JSONB`
- `common_errors JSONB`
- `difficulty smallint`
- `cognitive_level`
- `estimated_seconds`
- `source_type`
- `source_reference`
- `copyright_status`
- `review_status`
- `version`
- `embedding vector nullable`

### 6.2 question_curriculum_mappings

- `question_id`
- `textbook_id`
- `curriculum_node_id`
- `knowledge_point_id`
- `mapping_type`：primary/secondary
- `confidence`
- `reviewed_by`

### 6.3 question_quality_metrics

- 使用次数、正确率、平均用时、提示率、争议率、区分度、跳过率。

### 6.4 question_reviews

保存审核结论、问题类型和版本。

## 7. 练习与掌握度

### 7.1 practice_sessions

- `student_id`
- `practice_type`
- `term_id`
- `subject_id`
- `scope JSONB`
- `constraints JSONB`
- `status`
- `started_at`
- `finished_at`
- `score_summary JSONB`

### 7.2 practice_session_questions

保存题目顺序、题目版本和题目快照。

### 7.3 answer_records

- `session_id`
- `student_id`
- `question_id`
- `question_version`
- `answer JSONB`
- `is_correct`
- `score`
- `duration_seconds`
- `hint_count`
- `attempt_count`
- `answer_context JSONB`
- `submitted_at`

### 7.4 wrong_questions

- `student_id`
- `question_id`
- `knowledge_point_id`
- `first_wrong_at`
- `last_wrong_at`
- `wrong_count`
- `state`
- `next_review_at`
- `latest_answer_record_id`

唯一约束：`student_id, question_id`。

### 7.5 wrong_question_events

保存状态机事件：original_retest、similar、variant、forgotten 等。

### 7.6 mastery_records

- `student_id`
- `term_id`
- `knowledge_point_id`
- `score numeric(5,2)`
- `status`
- `evidence_count`
- `last_evaluated_at`
- `next_review_at`
- `components JSONB`

唯一约束：`student_id, term_id, knowledge_point_id`。

### 7.7 mastery_events

保存每次掌握度变化前后值、触发原因和证据。

## 8. 任务、行为与奖励

### 8.1 learning_tasks

- `student_id`
- `created_by_user_id`
- `task_type`
- `source_type`：ai_recommendation/parent/manual/system
- `payload JSONB`
- `due_at`
- `status`
- `estimated_minutes`
- `reward_points`

### 8.2 learning_events

记录页面、练习、提示、暂停、恢复和完成等行为；敏感内容不得直接进入事件表。

### 8.3 reward_ledger

使用积分账本而非直接修改余额：

- `student_id`
- `event_type`
- `points`
- `reference_type`
- `reference_id`
- `anti_abuse_result`

## 9. AI、任务和审计

### 9.1 ai_reports

- `student_id`
- `report_type`
- `date_from/date_to`
- `status`
- `input_snapshot JSONB`
- `metrics JSONB`
- `provider`
- `model`
- `template_version`
- `output_json JSONB`
- `output_text`
- `evidence_map JSONB`
- `error_message`

### 9.2 background_jobs

- `job_type`
- `resource_type/resource_id`
- `idempotency_key unique`
- `status`
- `attempts`
- `payload JSONB`
- `error`

### 9.3 audit_logs

- `actor_user_id`
- `family_id nullable`
- `action`
- `resource_type/resource_id`
- `before_data JSONB`
- `after_data JSONB`
- `request_id`
- `ip_hash`

## 10. 索引与隔离

重点索引：

- 所有学生业务表：`student_id, created_at`。
- 家庭资源：`family_id`。
- 题库过滤：`subject_id, review_status, difficulty`。
- 教材映射：`textbook_id, curriculum_node_id, knowledge_point_id`。
- 向量：根据数据量选择 HNSW。

应用层强制家庭范围；生产阶段评估 PostgreSQL Row Level Security。

## 11. 备份与保留

- 数据库每日全量备份，保留 7 天；每周备份保留 4 周。
- 原始图片默认 180 天，可由家长提前删除。
- 审计日志保留至少 1 年。
- 学期归档数据不得因升年级覆盖。
