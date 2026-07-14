# 学迹智评 API 设计说明书

## 1. 基本约定

- Base URL：`/api/v1`
- JSON 使用 UTF-8。
- 时间使用 ISO 8601 UTC。
- 主键使用 UUID。
- 列表接口使用 `page`、`page_size` 或游标分页。
- 写操作支持 `Idempotency-Key`。
- 认证使用 `Authorization: Bearer <access_token>`。

成功响应：

```json
{"data": {}, "meta": {"request_id": "..."}}
```

失败响应：

```json
{
  "error": {
    "code": "AUTH_002",
    "message": "权限不足",
    "request_id": "...",
    "details": {}
  }
}
```

## 2. 认证

### POST `/auth/register/parent`

创建家长账号。

### POST `/auth/login`

请求：

```json
{"account": "parent@example.com", "password": "***"}
```

响应 access_token、refresh_token 和用户摘要。

### POST `/auth/refresh`

刷新访问令牌并轮换 refresh_token。

### POST `/auth/logout`

撤销当前会话。

### GET `/auth/me`

返回当前用户和角色。

## 3. 家庭与学生

### GET `/families/current`

返回当前家庭、监护人和学生列表。

### POST `/students`

家长创建学生档案。

```json
{
  "nickname": "林小雨",
  "birth_date": "2015-05-01",
  "school_system": "6-3",
  "current_grade": 5,
  "daily_minutes_limit": 50
}
```

### GET `/students/{student_id}`

返回学生基础档案。

### PATCH `/students/{student_id}`

仅家长修改允许字段。

### POST `/students/{student_id}/terms`

创建或确认学期档案。

### POST `/students/{student_id}/terms/{term_id}/archive`

归档学期；需要主监护人确认。

## 4. 教材与进度

### GET `/subjects`

返回科目主数据。

### GET `/textbooks`

过滤参数：subject、grade、publisher、revision_year、volume。

### POST `/students/{student_id}/textbooks`

```json
{
  "term_id": "...",
  "subject_id": "...",
  "textbook_id": "..."
}
```

### PATCH `/students/{student_id}/textbooks/{assignment_id}/progress`

```json
{
  "current_node_id": "...",
  "source": "parent_confirmed"
}
```

### GET `/textbooks/{textbook_id}/tree`

返回教材目录与知识点树。

## 5. 上传与 OCR

### POST `/documents/upload`

`multipart/form-data`：

- file
- student_id
- document_type

响应：

```json
{
  "data": {
    "document_id": "...",
    "status": "uploaded",
    "duplicate_candidate": false
  }
}
```

### POST `/documents/{document_id}/ocr`

创建异步 OCR 任务。

### GET `/documents/{document_id}`

返回文档状态、OCR 原文、结构化候选和低置信度字段。文件地址使用短期签名 URL。

### POST `/documents/{document_id}/confirm`

仅绑定学生家长可调用。

```json
{
  "confirmed_data": {
    "exam_name": "第六单元测验",
    "scores": [{"subject": "数学", "score": 86, "full_score": 100}]
  }
}
```

### POST `/documents/{document_id}/reject`

```json
{"reason": "图片模糊，重新上传"}
```

## 6. 成绩与评语

### GET `/students/{student_id}/scores`

过滤 term_id、subject_id、date_from、date_to。

### POST `/students/{student_id}/scores/manual`

家长手工录入成绩。

### GET `/students/{student_id}/comments`

返回原文、标签、证据和确认状态。

### PATCH `/comments/{comment_id}/labels`

家长修正结构化标签，并保留修订历史。

## 7. 本地题库

### GET `/admin/questions`

后台筛选题目。

### POST `/admin/questions`

创建题目草稿。

### GET `/admin/questions/{question_id}`

返回完整题目与映射。

### PATCH `/admin/questions/{question_id}`

修改并增加版本。

### POST `/admin/questions/{question_id}/mappings`

创建教材和知识点映射。

### POST `/admin/questions/{question_id}/review`

```json
{"decision": "approve", "notes": "答案与解析已复核"}
```

### POST `/admin/questions/{question_id}/publish`

发布前执行完整性、版权和审核校验。

## 8. 练习与评测

### POST `/students/{student_id}/practice-sessions`

```json
{
  "practice_type": "targeted",
  "subject_id": "...",
  "knowledge_point_ids": ["..."],
  "question_count": 6,
  "estimated_minutes": 15
}
```

### GET `/practice-sessions/{session_id}`

返回会话状态和进度。

### GET `/practice-sessions/{session_id}/next`

返回下一题；不返回答案和完整解析。

### POST `/practice-sessions/{session_id}/answers`

```json
{
  "question_id": "...",
  "answer": {"selected": ["B"]},
  "duration_seconds": 72,
  "hint_count": 0
}
```

响应正确性、分层反馈和下一步；只有达到策略条件时返回解析。

### POST `/practice-sessions/{session_id}/finish`

结算并触发错题与掌握度更新。

### GET `/students/{student_id}/wrong-questions`

过滤状态、科目、知识点和下次复习时间。

### POST `/wrong-questions/{wrong_id}/retest`

创建原题、同类题或变式题复测。

### GET `/students/{student_id}/mastery`

返回知识点掌握度、证据量和复习建议。

## 9. 学习任务

### GET `/students/{student_id}/tasks`

### POST `/students/{student_id}/tasks`

家长推送任务。

```json
{
  "task_type": "practice",
  "title": "数学应用题专项",
  "payload": {"knowledge_point_ids": ["..."]},
  "estimated_minutes": 15,
  "due_at": "2026-07-16T12:00:00Z",
  "reward_points": 40
}
```

### PATCH `/tasks/{task_id}/status`

学生开始、暂停或完成任务。

## 10. AI 报告

### POST `/students/{student_id}/reports`

```json
{
  "report_type": "parent_weekly",
  "date_from": "2026-07-07",
  "date_to": "2026-07-14"
}
```

返回异步报告 ID。

### GET `/reports/{report_id}`

返回状态。完成后按角色返回允许查看的版本。

### GET `/students/{student_id}/reports`

返回报告历史、模型与模板版本，不返回模型密钥或内部提示词。

## 11. 打印

### POST `/print-jobs`

类型：practice、answer、explanation、wrong_book、knowledge_cards、student_report、parent_report。

### GET `/print-jobs/{job_id}`

完成后返回短期下载 URL。

## 12. 后台配置与监控

### GET `/admin/system/health`

返回数据库、Redis、OCR、主 AI 和备用 AI 状态；敏感细节脱敏。

### GET `/admin/data-quality`

返回 OCR 修改率、题目争议率、报告 Schema 通过率等。

### GET/PUT `/admin/settings/{group}`

配置报告模板版本、OCR 阈值、学习时长默认值等。真实 API Key 不通过普通查询接口返回。

## 13. 幂等与并发

- 文档确认、练习结算、积分发放和报告生成必须使用幂等键。
- 修改题目和资料确认使用乐观锁版本号。
- 同一练习题重复提交只接受第一次有效提交，除非业务明确允许重试。
