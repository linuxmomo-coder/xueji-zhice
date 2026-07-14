# 学迹智评详细设计说明书（LLD）

## 1. 代码组织

```text
backend/app/
├── api/
│   ├── deps.py
│   └── routes/
├── core/
│   ├── config.py
│   ├── security.py
│   └── logging.py
├── db/
│   ├── base.py
│   └── session.py
├── models/
├── schemas/
├── repositories/
├── services/
│   ├── auth/
│   ├── curriculum/
│   ├── ocr/
│   ├── question_bank/
│   ├── practice/
│   ├── mastery/
│   ├── reports/
│   └── printing/
├── workers/
└── main.py
```

MVP 骨架允许将模型和 Schema 合并到少量文件中，但模块接口必须与上述边界一致。

## 2. 核心领域对象

### 2.1 User

- `id: UUID`
- `email/phone`
- `password_hash`
- `role: parent|student|admin`
- `status`
- `created_at/updated_at`

### 2.2 Family 与 GuardianRelation

- Family 表示家庭数据隔离边界。
- GuardianRelation 连接家长与学生。
- `is_primary` 标记主监护人。
- 删除、导出、重新绑定等高风险操作必须校验主监护人。

### 2.3 StudentProfile

- 行政年级不直接代表各科学习水平。
- 当前学年、学期和学制独立保存。
- 科目水平保存于 `student_subject_levels`。

### 2.4 Textbook 与 StudentTextbook

- Textbook 保存教材主数据。
- StudentTextbook 保存学生在某学年/学期/科目使用的教材及进度。
- 切换教材时关闭旧关联并新增记录，禁止覆盖历史。

### 2.5 LearningDocument

用于表示上传的成绩、评语、评价、教材或进度图片。

状态：

```text
uploaded -> ocr_processing -> awaiting_confirmation
          -> ocr_failed
awaiting_confirmation -> confirmed | rejected
```

### 2.6 Question

题目主体不绑定唯一教材。通过 `question_curriculum_mappings` 映射到多个教材目录与知识点。

状态：`draft | ai_validating | pending_review | trial | active | suspended | retired`。

### 2.7 PracticeSession 与 AnswerRecord

- PracticeSession 保存一次练习/评测上下文。
- AnswerRecord 保存题目快照、学生答案、正确性、用时和提示。
- 题目修改后历史答题仍使用提交时快照。

### 2.8 WrongQuestion

状态机：

```text
new -> learning -> retest_pending
retest_pending -> original_passed | retest_failed
original_passed -> similar_passed
similar_passed -> variant_passed
variant_passed -> mastered
mastered -> suspected_forgotten
```

### 2.9 MasteryRecord

每个学生、知识点、学期一条当前记录，并保留 `mastery_events` 历史事件。

### 2.10 AIReport

保存报告类型、输入快照、指标、模型、模板、输出 JSON、输出文本、证据引用、状态和失败原因。

## 3. 服务接口

### 3.1 CurriculumService

```python
class CurriculumService:
    def assign_textbook(student_id, subject_id, textbook_id, term_id): ...
    def update_progress(student_id, textbook_id, node_id, source, confirmed_by): ...
    def archive_term(student_id, term_id): ...
```

规则：

- 当前教材同一科目只能有一条 active 记录。
- 换教材时历史关联变为 inactive。
- 推测进度不得直接标记 confirmed。

### 3.2 DocumentService

```python
class DocumentService:
    def create_upload(...): ...
    def request_ocr(document_id): ...
    def confirm(document_id, edited_fields, confirmer_id): ...
    def reject(document_id, reason, confirmer_id): ...
```

确认事务必须同时：

1. 校验文档归属。
2. 保存修订前后差异。
3. 创建正式成绩或评语记录。
4. 更新文档状态。
5. 写审计日志。
6. 发送领域事件。

### 3.3 QuestionBankService

```python
class QuestionBankService:
    def search(filters, pagination): ...
    def create_question(payload, operator_id): ...
    def map_curriculum(question_id, mappings): ...
    def publish(question_id, reviewer_id): ...
```

发布校验：

- 必须有标准答案和解析。
- 必须至少映射一个知识点。
- 版权状态必须允许当前用途。
- AI 生成题必须经过自动校验和人工审核。

### 3.4 PracticeService

```python
class PracticeService:
    def create_session(student_id, practice_type, scope, constraints): ...
    def get_next_question(session_id): ...
    def submit_answer(session_id, question_id, answer, metrics): ...
    def finish_session(session_id): ...
```

组题步骤：

1. 根据学生教材和已确认进度限定知识点。
2. 排除未学、停用、争议和版权不适用题目。
3. 排除最近出现的题目。
4. 按难度与认知层级配比抽取。
5. 插入必要的错题、同类题或变式题。
6. 校验总预计时长。

### 3.5 GradingService

客观题使用确定性规则：

- 单选：选项 ID 全等。
- 多选：集合全等，MVP 默认不做部分得分。
- 判断：布尔值全等。
- 填空：标准化空格、大小写、全半角后匹配可接受答案。
- 数值：支持容差和单位标准化。

### 3.6 WrongQuestionService

```python
class WrongQuestionService:
    def record_failure(answer_record): ...
    def record_retest_result(wrong_question_id, mode, passed): ...
    def schedule_review(wrong_question_id): ...
```

仅原题通过时状态到 `original_passed`，不得直接到 `mastered`。

### 3.7 MasteryService

MVP 可解释计算模型：

```text
score = correctness * 0.35
      + difficulty_adjusted * 0.15
      + no_hint_rate * 0.10
      + time_efficiency * 0.10
      + similar_transfer * 0.10
      + variant_transfer * 0.10
      + retest_stability * 0.10
```

- 样本少于 3 题：`insufficient_data`。
- 时间衰减后低于阈值：`suspected_forgotten`。
- 教师评语只作为报告证据，不直接修改知识点掌握度。

### 3.8 ReportService

```python
class ReportService:
    def build_snapshot(student_id, report_type, date_range): ...
    def generate(report_id): ...
    def validate_output(report_id): ...
```

生成流程：规则统计 → 脱敏 → 主模型 → Schema 校验 → 备用模型 → 内容校验 → 保存。

## 4. 权限设计

| 操作 | 学生 | 家长 | 管理员 |
|---|---:|---:|---:|
| 查看本人任务 | 是 | 可查看绑定学生 | 否，默认不可见 |
| 上传资料 | 是 | 是 | 技术排障受控 |
| 确认正式成绩/评语 | 否 | 是 | 否 |
| 修改学生教材 | 否 | 是 | 主数据管理 |
| 管理题库 | 否 | 否 | 是 |
| 查看完整敏感原图 | 本人资料 | 绑定学生 | 默认脱敏、授权后查看 |

所有业务查询除管理员主数据操作外，必须绑定 `family_id` 或 `student_id` 范围。

## 5. 异步任务

任务类型：

- `ocr_document`
- `structure_document`
- `generate_ai_report`
- `generate_pdf`
- `recalculate_mastery`

任务字段：`id, type, resource_id, status, attempts, idempotency_key, error, started_at, finished_at`。

重试规则：

- 网络错误指数退避，最多 3 次。
- Schema 校验失败允许修复提示重试 1 次。
- 业务校验失败不自动重试。
- 同一幂等键只能存在一个成功任务。

## 6. 错误码

| 错误码 | 含义 |
|---|---|
| AUTH_001 | 未认证 |
| AUTH_002 | 权限不足 |
| FAMILY_001 | 非绑定家庭资源 |
| DOC_001 | 不支持的资料类型 |
| DOC_002 | 文档状态不允许当前操作 |
| OCR_001 | OCR 失败 |
| BANK_001 | 题目未审核 |
| PRACTICE_001 | 练习已结束 |
| REPORT_001 | 数据不足 |
| REPORT_002 | 模型输出结构无效 |

统一错误响应：

```json
{
  "error": {
    "code": "DOC_002",
    "message": "当前资料状态不允许确认",
    "request_id": "...",
    "details": {}
  }
}
```

## 7. 日志与审计

应用日志记录 request_id、用户 ID、路由、状态码和耗时，不记录敏感正文。

审计日志记录：

- 成绩/评语确认与修改。
- 学生教材和年级变更。
- 题目发布、下架和答案修改。
- 数据导出和删除。
- AI/OCR 配置修改。

## 8. 测试策略

- 单元测试：判题、错题状态机、掌握度、权限范围。
- 集成测试：上传确认事务、练习提交、报告编排。
- 合约测试：百炼、混元和 PaddleOCR 适配器。
- E2E：家长建档、学生练习、家长确认资料、生成报告。
