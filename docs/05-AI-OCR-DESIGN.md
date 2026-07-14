# 学迹智评 AI 与 OCR 设计说明书

## 1. 设计边界

AI 和 OCR 只承担适合概率模型的任务，不替代确定性业务规则。

MVP 支持：

- 成绩单、教师评语、学校评价、教材封面与目录识别。
- OCR 结果结构化。
- 教师评语标签提取。
- 学生版和家长版报告。
- 学习方案建议和自然语言鼓励。

MVP 不支持：

- 整张试卷拆题。
- 纸质作业答案识别。
- 自动提取纸质错题。
- 高风险主观题自动定分。
- AI 生成题未经审核直接进入正式题库。

## 2. OCR 架构

### 2.1 主流程

```text
图片上传
  -> 文件安全与质量检测
  -> 版面方向与裁切
  -> PaddleOCR
  -> 文本/表格结果标准化
  -> 文档类型结构化
  -> 置信度计算
  -> 家长确认
  -> 正式入档
```

### 2.2 OCR 输出统一格式

```json
{
  "document_type": "score_comment",
  "pages": [
    {
      "page": 1,
      "blocks": [
        {
          "text": "数学 86分",
          "bbox": [10, 20, 120, 55],
          "confidence": 0.98,
          "block_type": "text"
        }
      ]
    }
  ],
  "raw_text": "...",
  "engine": "paddleocr",
  "engine_version": "..."
}
```

### 2.3 成绩结构化 Schema

```json
{
  "student_name": {"value": "林小雨", "confidence": 0.96},
  "exam_name": {"value": "第六单元测验", "confidence": 0.91},
  "exam_date": {"value": "2026-07-14", "confidence": 0.88},
  "scores": [
    {
      "subject": "数学",
      "score": 86,
      "full_score": 100,
      "class_average": 81,
      "class_rank": 12,
      "confidence": 0.97
    }
  ]
}
```

关键数值字段置信度低于 0.95 必须显著提示确认；普通文字低于 0.90 标记。

### 2.4 评语结构化 Schema

维度：课堂专注、参与度、基础知识、理解能力、迁移应用、表达、作业完成、订正、独立性、时间管理、主动性、合作、情绪信心、教师建议。

```json
{
  "original_text": "课堂认真，应用题容易忽略条件。",
  "labels": [
    {
      "dimension": "课堂专注",
      "level": "良好",
      "sentiment": "positive",
      "evidence": "课堂认真",
      "confidence": 0.96
    },
    {
      "dimension": "迁移应用",
      "level": "需要加强",
      "sentiment": "improvement",
      "evidence": "应用题容易忽略条件",
      "confidence": 0.91
    }
  ]
}
```

禁止模型生成原文中不存在的评价。

## 3. AI 提供商适配

统一接口：

```python
class LLMProvider:
    async def generate_json(
        self,
        system_prompt: str,
        user_payload: dict,
        response_schema: dict,
        timeout_seconds: int,
    ) -> dict: ...
```

实现：

- `BailianProvider`：主模型。
- `HunyuanProvider`：备用模型。
- `MockProvider`：本地开发与测试。

切换条件：

- 连接超时。
- 429 限流。
- 5xx 错误。
- 连续输出不符合 Schema。

业务数据不足、权限错误和内容校验失败不得通过切换供应商掩盖。

## 4. 数据准备原则

发送给 AI 的内容只包含完成任务所需的最小数据：

- 使用内部学生 ID，不发送真实姓名。
- 学校名称和教师姓名默认不发送。
- OCR 原图不直接发送给文本模型。
- 成绩、评语证据和题库指标按报告时间范围聚合。
- 不发送密码、联系方式、地址或 API Key。

## 5. 报告生成架构

### 5.1 规则层

AI 调用前由确定性程序计算：

- 成绩趋势。
- 学习时长和有效做题比例。
- 正确率、提示率、复测通过率。
- 掌握度分布。
- 数据样本量和可信度。
- 优势与薄弱知识点候选。

### 5.2 学生版输出 Schema

```json
{
  "summary": "...",
  "progress": ["..."],
  "strengths": ["..."],
  "challenges": ["..."],
  "evidence": [
    {"statement": "...", "evidence_ids": ["metric:math_accuracy"]}
  ],
  "next_tasks": [
    {"title": "...", "minutes": 15, "reason": "..."}
  ],
  "method_tip": "...",
  "encouragement": "...",
  "insufficient_data": ["作文"],
  "next_review_condition": "完成本周复测"
}
```

要求：

- 避免固定人格标签。
- 挑战项最多 2 个。
- 语言适合对应年龄。
- 鼓励必须对应具体学习行为。

### 5.3 家长版输出 Schema

```json
{
  "executive_summary": "...",
  "data_quality": {"level": "medium", "limitations": []},
  "school_performance": "...",
  "teacher_comment_summary": "...",
  "question_bank_performance": "...",
  "dimensions": [
    {"name": "知识掌握", "score": 81, "evidence_ids": []}
  ],
  "strengths": [],
  "issues": [],
  "possible_causes": [],
  "two_week_actions": [
    {"action": "每天15分钟应用题", "measure": "复测达到80%"}
  ],
  "parent_communication": [],
  "risks": [],
  "insufficient_data": [],
  "next_review_condition": "..."
}
```

建议数量上限：两周行动 3 条、家长沟通建议 3 条。

## 6. 结论可信度

每个结论分级：

- `fact`：直接数据事实。
- `high_confidence`：至少两个独立来源一致，且样本充分。
- `possible`：存在支持证据但不足以确定。
- `insufficient_data`：样本或覆盖不足。

AI 输出必须携带 evidence_ids，服务端校验证据是否存在。

## 7. 提示词管理

- 提示词保存在数据库或版本化文件中。
- 每次报告保存 `template_version`。
- 系统提示词禁止直接拼接用户原始指令。
- 用户文本按数据字段传入，不作为系统指令。
- 使用 JSON Schema 或结构化输出能力。

## 8. AI 生成题

仅进入草稿/试用流程：

1. 选择已审核知识点和母题约束。
2. 生成题目、答案、解析和标签。
3. 使用确定性程序或第二模型复算。
4. 重复题与语义相似度检查。
5. 难度与超纲检查。
6. 人工审核。
7. 试用数据达标后发布。

## 9. 质量评估

### OCR 指标

- 字段准确率。
- 数字字段准确率。
- 家长修改率。
- 低置信度召回率。
- 文档重复识别率。

### AI 指标

- JSON Schema 通过率。
- 证据引用有效率。
- 无依据结论率。
- 家长采纳率。
- 报告投诉率。
- 主备切换率。
- 单报告 Token 和成本。

## 10. 降级策略

- OCR 不可用：允许人工录入。
- AI 不可用：展示规则统计报告和模板化建议。
- 主模型不可用：切换混元。
- 两个模型均失败：报告状态标记失败，不生成虚假内容。
- 数据不足：生成数据不足报告，不强行给出结论。
