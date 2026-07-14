# 学迹智评｜题库导入、媒体存储与填空题答案归一化设计

> 状态：需求与设计收集，暂不修改当前 MVP 业务代码。

## 1. 设计目标

本设计解决以下问题：

1. 将标准 Excel 题库包经过校验、审核后导入项目题库；
2. 题图不得长期依赖第三方网络链接，必须进入项目自有存储；
3. 数据库保存题图的可控引用、摘要和元数据，而不是只保存不可控外链；
4. 填空题判分不能只做原始字符串相等比较；
5. 正确处理大小写、全角半角、空格、根号、分数、比号、角度和多个等价答案；
6. 所有导入、图片迁移和答案规则变更都可追溯、可回滚。

## 2. 当前 20 题 Excel 导入包检查结论

上传文件包含：

- `questions_import`：20 道题；
- `knowledge_mappings`：20 条知识点映射候选；
- `source_manifest`：来源与版权说明；
- `校验结果`：题目数量、题号唯一性、JSON 合法性、题图链接等检查均通过；
- 所有题目均为八年级数学；
- 所有题图均标记为必需；
- 所有题目版权状态均为 `pending_review`；
- 所有内容审核状态均为 `pending`。

该文件适合作为“导入暂存包”，但当前代码不能直接写入，原因如下：

| Excel 字段 | 当前代码字段 | 处理方式 |
|---|---|---|
| `question_code` | `Question.question_code` | 可直接映射 |
| `subject_code=MATH` | `Question.subject` | 转换为“数学” |
| `grade_id=8` | `Question.grade` | 可直接映射 |
| `knowledge_point_text` | `Question.knowledge_point` | MVP 可暂存文字；正式版解析为知识点 ID |
| `question_type` | `Question.question_type` | 枚举校验后映射 |
| `difficulty` | `Question.difficulty` | 可直接映射 |
| `cognitive_level=apply/analyze` | 当前使用 application/analysis | 需要枚举转换 |
| `stem` 为 JSON 对象 | 当前 `stem` 为 Text | 当前提取 `stem.text`；正式版升级为 JSONB 或内容块表 |
| `options` 为 JSON 数组 | 当前数据库列为 JSON | 可存，但 Python 类型应改为列表型声明 |
| `answer` 为 JSON | 当前 `answer` 为 JSON | 升级为答案规则结构后导入 |
| `explanation` 为 JSON 对象 | 当前 `explanation` 为 Text | 当前提取 `explanation.text`；正式版保留结构化内容 |
| `source_reference` | 当前模型未落地 | 增加字段或来源表 |
| `common_errors` | 当前模型未落地 | 增加 JSONB 字段 |
| `version` | 当前模型未落地 | 增加版本字段 |
| `image_url` | 当前没有题图资产表 | 下载到自有存储后建立资产记录 |
| `subject_id/textbook_id/knowledge_point_id` | 文件中为空 | 导入时根据代码和文字标签解析 |

即使完成导入，`review_status=pending` 的题目也不能直接推送给学生；只有人工审核通过并改为 `active` 后才能进入练习。

## 3. 推荐导入流程

```text
上传 Excel
  → 创建导入批次
  → 读取工作表和 JSON 字段
  → 校验题号、枚举、必填字段、JSON、版权状态
  → 解析科目/年级/教材/知识点 ID
  → 下载并校验题图
  → 上传到项目自有对象存储
  → 生成题目与资产暂存记录
  → 后台人工预览和抽查
  → 审核通过
  → 事务写入正式题库
  → 输出成功、失败和警告明细
```

### 3.1 导入必须支持的模式

- `validate_only`：只校验，不写数据库；
- `staging`：写入暂存区，等待审核；
- `commit`：审核后写入正式题库；
- `rollback`：按导入批次撤销未被学生使用的新增记录；
- `upsert`：按 `question_code` 判断新增或版本升级，禁止静默覆盖。

### 3.2 建议新增表

#### question_import_batches

- `id`
- `file_name`
- `file_sha256`
- `status`
- `mode`
- `total_rows`
- `valid_rows`
- `warning_rows`
- `failed_rows`
- `created_by_user_id`
- `started_at`
- `finished_at`
- `summary JSONB`

#### question_import_rows

- `batch_id`
- `row_no`
- `question_code`
- `raw_data JSONB`
- `normalized_data JSONB`
- `status`
- `errors JSONB`
- `warnings JSONB`
- `created_question_id nullable`

导入过程必须以数据库事务和幂等键保护，不得导入一半后留下不可识别的脏数据。

## 4. 题图和其他媒体的存储方案

### 4.1 结论

题图应当进入项目自己的存储体系，但不建议把大批图片二进制直接存入 PostgreSQL。

推荐架构：

```text
题图二进制
  → 开发环境：MinIO
  → 生产环境：腾讯云 COS

PostgreSQL
  → 保存 asset_id、object_key、SHA-256、MIME、尺寸、大小和来源信息
```

数据库中不能只保存第三方 `raw.githubusercontent.com` 链接，因为外部文件可能被删除、改名、限流或停止访问。

### 4.2 建议新增 question_assets 表

- `id uuid PK`
- `question_id uuid FK`
- `asset_type`：stem_image/explanation_image/option_image/audio/attachment
- `storage_provider`：minio/cos
- `bucket`
- `object_key`
- `mime_type`
- `size_bytes`
- `width`
- `height`
- `sha256`
- `alt_text`
- `sort_order`
- `is_required`
- `source_url nullable`：仅用于来源追溯，不用于前端直接展示
- `source_reference JSONB`
- `status`
- `created_at`

前端获取图片时，由后端返回短期签名 URL 或经过 CDN 的受控 URL。数据库保存的是稳定资产标识和对象键，不依赖外部原始链接。

### 4.3 是否可以把图片直接放数据库

技术上可使用 PostgreSQL `bytea` 或 Large Object，但本项目不建议作为默认方案，原因：

- 数据库体积和备份体积快速膨胀；
- 图片读取会占用数据库连接和网络吞吐；
- CDN、缩略图和缓存处理不便；
- 数据库恢复时间显著增加；
- 题库批量导入时性能较差。

只有非常小且必须与事务强绑定的文件才可考虑 `bytea`。普通题图统一使用 MinIO/COS。

### 4.4 导入图片安全检查

- 仅允许白名单 MIME：PNG/JPEG/WebP/SVG（SVG 必须清洗）；
- 限制单图大小和像素尺寸；
- 下载后计算 SHA-256；
- 根据摘要去重；
- 验证真实文件类型，不相信扩展名和 HTTP Header；
- 禁止跟随无限重定向；
- 设置下载超时和域名白名单；
- 下载失败的必需图片会阻止题目发布；
- 保留原始来源 URL 和提交版本，仅用于审计。

## 5. 填空题答案数据结构

不得只保存：

```json
{"type":"fill_blank","value":"3√3"}
```

建议升级为：

```json
{
  "type": "fill_blank",
  "blanks": [
    {
      "id": "blank_1",
      "mode": "math_expression",
      "accepted_answers": [
        "3√3",
        "3*sqrt(3)",
        "3\\sqrt{3}"
      ],
      "case_sensitive": false,
      "order_sensitive": true,
      "unit": null,
      "unit_required": false,
      "absolute_tolerance": 0,
      "relative_tolerance": 0,
      "normalization_profile": "math_zh_v1"
    }
  ]
}
```

多空题每个空单独配置，不能把整道题所有答案拼成一个字符串。

## 6. 答案归一化规则

### 6.1 通用文本归一化

按以下顺序处理：

1. Unicode NFKC 归一化；
2. 去除首尾空白；
3. 连续空格压缩；
4. 全角英文字母、数字和标点转半角；
5. 中文括号、逗号、冒号按题目配置统一；
6. `−`、`–`、`—` 统一为负号 `-`；
7. 不可见字符和零宽字符清理；
8. 英文文本按配置做大小写折叠；
9. 保留原始答案和归一化答案，便于审计。

大小写不能全局强制忽略。示例：

- 英语单词填空通常可配置 `case_sensitive=false`；
- 化学元素符号 `Co` 与 `CO` 不等价，应配置 `case_sensitive=true`；
- 数学变量若题目明确区分大小写，也必须保留。

### 6.2 数学符号归一化

统一识别以下输入：

- 根号：`√3`、`sqrt(3)`、`\sqrt{3}`；
- 乘号：`×`、`*`、`·`；
- 除号和分数：`÷`、`/`、`½` 等；
- 比号：`:`、`∶`；
- 角度：`68`、`68°` 是否等价由 `unit_required` 决定；
- 括号：全角和半角括号；
- 幂：`x²`、`x^2`；
- 圆周率：`π`、`pi`；
- 正负号：`±` 需要解析为答案集合，不能当普通字符比较。

### 6.3 数学等价判定

数学填空题采用“安全解析 + 符号等价”而不是字符串比较：

1. 将输入转换为受限数学表达式 AST；
2. 禁止 Python `eval` 和任意函数调用；
3. 对标准答案与学生答案进行化简；
4. 两者差值可化简为 0 时判定等价；
5. 数值答案可配置绝对/相对误差；
6. 比例答案统一约分后比较；
7. 分数与小数根据题目规则判断是否允许等价；
8. 含单位时先拆分数值和单位，再分别比较；
9. 无法可靠解析时转人工/规则复核，不调用大模型直接决定分数。

示例：

| 标准答案 | 学生输入 | 判定条件 |
|---|---|---|
| `3√3` | `3*sqrt(3)` | 等价 |
| `3√3` | `√27` | 符号化简后等价 |
| `7∶4` | `7:4` | 比号归一化后等价 |
| `7∶4` | `14:8` | 允许比例约分时等价 |
| `68°` | `68` | 仅在单位非必填时等价 |
| `1/2` | `0.5` | 根据题目 `allow_decimal_equivalent` 配置 |
| `x+1` | `1+x` | 符号化简后等价 |
| `20/3°或100/3°` | `100/3°,20/3°` | 多答案无序模式下等价 |

### 6.4 多答案和“或”关系

类似本批题目的：

```text
20/3°或100/3°
```

应存为答案数组，而不是包含“或”的单字符串：

```json
{
  "mode": "answer_set",
  "order_sensitive": false,
  "accepted_sets": [
    ["20/3°", "100/3°"]
  ]
}
```

### 6.5 不能自动等价处理的情况

以下情况必须保守处理：

- 开放性文字答案；
- 证明题关键步骤；
- 定义域不同导致形式看似等价；
- 近似值精度未说明；
- 单位换算规则不明确；
- 多个空之间存在联动；
- 答案来源本身仍处于 `pending_review`。

## 7. 建议的判分结果结构

```json
{
  "is_correct": true,
  "score": 1,
  "raw_answer": "３＊ＳＱＲＴ（３）",
  "normalized_answer": "3*sqrt(3)",
  "matched_answer": "3√3",
  "match_method": "symbolic_equivalence",
  "normalization_steps": ["NFKC", "case_fold", "sqrt_alias"],
  "confidence": 1.0,
  "needs_review": false
}
```

这样后续能够分析学生是格式输入问题、单位遗漏、运算错误还是知识错误，避免把输入法差异误判成错题。

## 8. 测试要求

至少覆盖：

- 全角数字和字母；
- 大小写敏感与不敏感；
- 前后空格和零宽字符；
- 根号三种输入；
- 分数、小数、百分数；
- 负号和不同减号字符；
- 比号与约分；
- 角度符号；
- 多答案顺序变化；
- 多空题；
- 单位必填和非必填；
- 恶意表达式和超长输入；
- 无法解析时的保守降级。

## 9. 实施顺序

### P0：题库导入基础

- 导入批次和行级校验；
- 当前 Excel 到 Question 模型的字段转换；
- 图片下载到 MinIO/COS；
- 后台预览、审核和发布；
- 题号幂等和版本控制。

### P1：填空题可靠判分

- 答案规则 Schema；
- NFKC 与符号归一化；
- 安全数学解析器；
- 根式、分数、比例、角度和多答案判定；
- 判分解释和完整测试。

### P2：正式知识体系映射

- 科目、教材、章节和知识点 ID 解析；
- 无法解析的记录进入人工映射队列；
- 与题型归纳、错题画像和相似题推荐联动。
