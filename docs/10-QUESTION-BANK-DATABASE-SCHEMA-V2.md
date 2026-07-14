# 学迹智评｜题库数据库结构 V2

> 状态：正式设计基线。当前仅更新设计文档，尚未执行数据库迁移和业务代码改造。

## 1. 设计原则

题库不能只使用一张 `questions` 大表保存所有内容。正式结构应满足：

1. 题目身份与题目内容版本分离；
2. 题干、选项、答案规则、解析和媒体资产分离；
3. 图片文件进入 MinIO/COS，数据库保存稳定资产记录；
4. 填空题、多空题、数学表达式和多答案采用结构化判分规则；
5. 教材、章节、知识点和题型标签采用多对多映射；
6. 来源、版权、审核、导入、勘误和历史重判可追溯；
7. 相似题推荐依赖结构化标签，向量只用于辅助排序；
8. 已发布版本不得被静默覆盖。

## 2. 核心关系

```text
questions                     题目稳定身份
  └── question_versions       题目内容版本
        ├── question_options
        ├── question_response_fields
        │     └── question_answer_rules
        ├── question_version_assets
        │     └── question_assets
        ├── question_curriculum_mappings
        ├── question_taxonomy_mappings
        ├── question_reviews
        └── question_embeddings

questions
  ├── question_sources
  ├── question_quality_metrics
  ├── question_relations
  └── question_error_reports

question_import_batches
  └── question_import_rows
```

## 3. questions：题目主表

只保存题目的稳定身份、生命周期和当前版本指针，不直接保存可频繁修改的题干和答案。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 题目内部 ID |
| question_code | varchar(80) unique | 是 | 对外稳定编码，导入和追踪使用 |
| subject_id | uuid FK | 是 | 科目 ID |
| base_grade | smallint | 是 | 基准年级，1—12 |
| lifecycle_status | varchar(30) | 是 | draft/active/suspended/retired/deleted |
| current_version_id | uuid FK nullable | 否 | 当前正式版本 |
| source_id | uuid FK nullable | 否 | 主要来源记录 |
| created_by_user_id | uuid FK nullable | 否 | 创建人 |
| first_published_at | timestamptz nullable | 否 | 首次发布时间 |
| suspended_reason | varchar(200) nullable | 否 | 暂停推荐原因，如疑似错误 |
| retired_at | timestamptz nullable | 否 | 停用时间 |
| created_at | timestamptz | 是 | 创建时间 |
| updated_at | timestamptz | 是 | 更新时间 |

关键约束：

- `question_code` 全库唯一；
- `current_version_id` 必须属于本题；
- `active` 题目必须存在已发布版本；
- 发现高风险勘误时将 `lifecycle_status` 改为 `suspended`，而不是删除。

## 4. question_versions：题目版本表

保存题目每个版本的实际内容与通用属性。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 版本 ID |
| question_id | uuid FK | 是 | 所属题目 |
| version_no | integer | 是 | 从 1 开始递增 |
| display_type | varchar(40) | 是 | single_choice/multiple_choice/fill_blank/calculation/short_answer/composite 等 |
| stem_content | jsonb | 是 | 结构化题干内容块 |
| explanation_content | jsonb nullable | 否 | 结构化解析内容块 |
| difficulty | smallint | 是 | 1—5 |
| cognitive_level | varchar(30) | 是 | remember/understand/application/analysis/evaluation/creation |
| estimated_seconds | integer | 是 | 预计用时 |
| language_code | varchar(10) | 是 | 默认 zh-CN |
| scoring_mode | varchar(30) | 是 | auto/rule/manual/hybrid |
| total_score | numeric(8,2) | 是 | 题目总分 |
| common_errors | jsonb nullable | 否 | 常见错误及解释 |
| answer_summary | varchar(500) nullable | 否 | 后台快速预览，不作为判分依据 |
| content_checksum | varchar(64) | 是 | 内容摘要，用于去重和版本一致性 |
| review_status | varchar(30) | 是 | draft/pending_review/approved/rejected |
| publication_status | varchar(30) | 是 | unpublished/published/superseded |
| change_summary | text nullable | 否 | 本版本修改说明 |
| created_by_user_id | uuid FK nullable | 否 | 创建人 |
| reviewed_by_user_id | uuid FK nullable | 否 | 审核人 |
| reviewed_at | timestamptz nullable | 否 | 审核时间 |
| published_at | timestamptz nullable | 否 | 发布时间 |
| created_at | timestamptz | 是 | 创建时间 |

唯一约束：`(question_id, version_no)`。

`stem_content` 推荐结构：

```json
{
  "blocks": [
    {"type": "text", "value": "如图，在△ABC中……"},
    {"type": "asset", "asset_ref": "asset-key-1"},
    {"type": "latex", "value": "AB=AC"}
  ]
}
```

## 5. question_options：选择题选项表

选择题选项独立存储，便于选项图片、排序和随机展示。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 选项 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| option_key | varchar(20) | 是 | A/B/C/D 或内部键 |
| content | jsonb | 是 | 文本、公式、图片等内容块 |
| sort_order | integer | 是 | 展示顺序 |
| is_fixed_position | boolean | 是 | 是否禁止随机排序 |
| metadata | jsonb nullable | 否 | 干扰项类型等扩展信息 |

唯一约束：`(question_version_id, option_key)`。

正确选项不要只依赖 `is_correct` 字段，应由判分规则统一定义，避免多选题和组合题规则分散。

## 6. question_response_fields：作答字段表

一题可以有多个作答区域，例如两个填空、一个计算结果加一个理由。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 作答字段 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| field_key | varchar(40) | 是 | blank_1、choice_1、result 等 |
| field_type | varchar(40) | 是 | single_choice/multiple_choice/text/number/math_expression/set/ordered_list/upload |
| prompt | varchar(300) nullable | 否 | 作答区域提示 |
| sort_order | integer | 是 | 顺序 |
| required | boolean | 是 | 是否必答 |
| score_weight | numeric(8,2) | 是 | 本字段分值 |
| input_config | jsonb nullable | 否 | 键盘、公式输入、字符限制等 |
| created_at | timestamptz | 是 | 创建时间 |

唯一约束：`(question_version_id, field_key)`。

## 7. question_answer_rules：判分规则表

每个作答字段可以有一条或多条判分规则。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 规则 ID |
| response_field_id | uuid FK | 是 | 对应作答字段 |
| rule_type | varchar(40) | 是 | choice_set/exact_text/normalized_text/numeric_tolerance/symbolic_equivalence/set_equivalence/manual |
| accepted_values | jsonb nullable | 否 | 标准答案集合 |
| normalization_profile | varchar(40) nullable | 否 | text_zh_v1/math_zh_v1/english_word_v1 等 |
| case_sensitive | boolean | 是 | 是否区分大小写 |
| order_sensitive | boolean | 是 | 多答案是否要求顺序 |
| allow_fullwidth_equivalent | boolean | 是 | 是否接受全角半角等价 |
| allow_fraction_decimal_equivalent | boolean | 是 | 分数与小数是否允许等价 |
| unit | varchar(40) nullable | 否 | 标准单位 |
| unit_required | boolean | 是 | 单位是否必填 |
| absolute_tolerance | numeric nullable | 否 | 绝对误差 |
| relative_tolerance | numeric nullable | 否 | 相对误差 |
| parser_profile | varchar(40) nullable | 否 | 数学解析器白名单配置 |
| parse_failure_action | varchar(30) | 是 | incorrect/manual_review |
| rule_version | integer | 是 | 判分规则版本 |
| metadata | jsonb nullable | 否 | 其他限制 |
| created_at | timestamptz | 是 | 创建时间 |

示例：根式填空题可接受 `3√3`、`sqrt(27)` 和 `3\sqrt{3}`，但系统最终通过符号等价判断，不靠字符串穷举。

关键原则：

- 禁止使用 Python `eval`；
- 大小写按题目配置，不能全局忽略；
- Unicode NFKC 处理全角半角；
- 无法安全解析时进入人工复核或保守判错；
- 学生原始输入和归一化结果都必须保留在答题记录中。

## 8. question_assets：题目媒体资产表

图片、音频和附件文件保存在 MinIO/COS，数据库保存资产元数据。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 资产 ID |
| storage_provider | varchar(20) | 是 | minio/cos |
| bucket | varchar(100) | 是 | 存储桶 |
| object_key | varchar(500) | 是 | 对象键，不保存临时签名链接 |
| mime_type | varchar(100) | 是 | 文件 MIME |
| size_bytes | bigint | 是 | 文件大小 |
| width | integer nullable | 否 | 图片宽度 |
| height | integer nullable | 否 | 图片高度 |
| sha256 | varchar(64) | 是 | 内容摘要与去重依据 |
| alt_text | varchar(500) nullable | 否 | 无障碍描述 |
| source_url | text nullable | 否 | 原始外链，仅用于追溯 |
| source_metadata | jsonb nullable | 否 | 原始仓库、提交号、版权说明等 |
| status | varchar(30) | 是 | active/quarantined/deleted |
| created_at | timestamptz | 是 | 创建时间 |

建议唯一索引：`(storage_provider, bucket, object_key)` 和 `sha256`。

## 9. question_version_assets：版本与资产关系表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 关系 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| asset_id | uuid FK | 是 | 资产 ID |
| asset_role | varchar(40) | 是 | stem_image/explanation_image/option_image/audio/attachment |
| option_key | varchar(20) nullable | 否 | 选项图片对应的选项键 |
| sort_order | integer | 是 | 排序 |
| is_required | boolean | 是 | 缺失时是否禁止发布 |
| display_config | jsonb nullable | 否 | 尺寸、位置、裁剪等 |

## 10. question_curriculum_mappings：教材与知识点映射

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 映射 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| subject_id | uuid FK | 是 | 科目 |
| textbook_id | uuid FK nullable | 否 | 教材 |
| curriculum_node_id | uuid FK nullable | 否 | 单元、章节或课时 |
| knowledge_point_id | uuid FK | 是 | 知识点 |
| mapping_type | varchar(20) | 是 | primary/secondary/prerequisite |
| source | varchar(20) | 是 | manual/ai/import |
| confidence | numeric(5,4) nullable | 否 | AI或导入置信度 |
| review_status | varchar(30) | 是 | pending/approved/rejected |
| reviewed_by_user_id | uuid FK nullable | 否 | 审核人 |
| created_at | timestamptz | 是 | 创建时间 |

一道题允许映射多个教材和知识点，但必须有一个主知识点。

## 11. question_taxonomy_nodes：题型分类树

统一管理题型族、题型模板、考查技能、错误模式和表达形式。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 分类节点 ID |
| subject_id | uuid FK | 是 | 科目 |
| parent_id | uuid FK nullable | 否 | 父节点 |
| dimension | varchar(30) | 是 | family/template/skill/error_pattern/expression |
| code | varchar(100) | 是 | 稳定编码 |
| name | varchar(200) | 是 | 名称 |
| description | text nullable | 否 | 说明 |
| status | varchar(30) | 是 | active/retired |
| sort_order | integer | 是 | 排序 |

唯一约束：`(subject_id, code)`。

## 12. question_taxonomy_mappings：题目特征标签

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 映射 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| taxonomy_node_id | uuid FK | 是 | 分类节点 |
| source | varchar(20) | 是 | manual/ai/import/data_feedback |
| confidence | numeric(5,4) nullable | 否 | AI置信度 |
| model_name | varchar(100) nullable | 否 | AI模型 |
| model_version | varchar(100) nullable | 否 | 模型版本 |
| review_status | varchar(30) | 是 | pending/approved/rejected |
| reviewed_by_user_id | uuid FK nullable | 否 | 审核人 |
| created_at | timestamptz | 是 | 创建时间 |

人工标签不能被 AI 静默覆盖。

## 13. question_sources：题目来源与版权表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 来源 ID |
| source_type | varchar(30) | 是 | self_built/authorized/public_domain/adapted/imported |
| source_name | varchar(200) nullable | 否 | 来源名称 |
| source_reference | text nullable | 否 | 原始页面、文档或题号 |
| source_url | text nullable | 否 | 原始链接 |
| license_type | varchar(100) nullable | 否 | 授权类型 |
| copyright_status | varchar(30) | 是 | owned/authorized/public_domain/pending_review/prohibited |
| authorization_file_asset_id | uuid FK nullable | 否 | 授权文件资产 |
| valid_from | date nullable | 否 | 授权开始日期 |
| valid_to | date nullable | 否 | 授权结束日期 |
| metadata | jsonb nullable | 否 | 版权补充信息 |
| created_at | timestamptz | 是 | 创建时间 |

`pending_review` 或 `prohibited` 来源不得发布给学生。

## 14. question_reviews：题目审核记录

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 审核 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| review_type | varchar(30) | 是 | content/answer/copyright/curriculum/technical |
| reviewer_user_id | uuid FK nullable | 否 | 审核人 |
| decision | varchar(30) | 是 | approved/rejected/changes_requested |
| issues | jsonb nullable | 否 | 问题列表 |
| comment | text nullable | 否 | 审核说明 |
| created_at | timestamptz | 是 | 审核时间 |

正式发布至少需要内容、答案和版权审核通过。

## 15. question_quality_metrics：题目质量指标

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| question_id | uuid PK/FK | 是 | 题目 ID |
| usage_count | bigint | 是 | 使用次数 |
| correct_rate | numeric(6,5) nullable | 否 | 正确率 |
| avg_duration_seconds | numeric nullable | 否 | 平均用时 |
| hint_rate | numeric(6,5) nullable | 否 | 提示使用率 |
| skip_rate | numeric(6,5) nullable | 否 | 跳过率 |
| dispute_rate | numeric(6,5) nullable | 否 | 勘误或争议率 |
| discrimination | numeric nullable | 否 | 区分度 |
| quality_score | numeric(5,2) nullable | 否 | 综合质量分 |
| last_calculated_at | timestamptz nullable | 否 | 最近计算时间 |

此表是汇总表，原始答题数据仍保存在答题域。

## 16. question_embeddings：向量索引表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 向量记录 ID |
| question_version_id | uuid FK | 是 | 题目版本 |
| embedding_type | varchar(30) | 是 | stem/solution/combined |
| model_name | varchar(100) | 是 | 向量模型 |
| model_version | varchar(100) | 是 | 模型版本 |
| embedding | vector | 是 | pgvector 向量 |
| content_checksum | varchar(64) | 是 | 生成向量时的内容摘要 |
| created_at | timestamptz | 是 | 创建时间 |

向量只能用于候选召回或排序，不能代替教材进度、知识点和题型硬过滤。

## 17. question_relations：题目关系表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 关系 ID |
| from_question_id | uuid FK | 是 | 来源题目 |
| to_question_id | uuid FK | 是 | 目标题目 |
| relation_type | varchar(30) | 是 | similar/variant/easier/harder/same_template |
| similarity_score | numeric(6,5) nullable | 否 | 相似度 |
| source | varchar(20) | 是 | manual/ai/data |
| review_status | varchar(30) | 是 | pending/approved/rejected |
| metadata | jsonb nullable | 否 | 推荐解释等 |
| created_at | timestamptz | 是 | 创建时间 |

## 18. question_import_batches 与 question_import_rows

### question_import_batches

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | 导入批次 |
| file_name | varchar(255) | 文件名 |
| file_sha256 | varchar(64) unique | 文件摘要与幂等键 |
| mode | varchar(20) | validate_only/staging/commit/upsert |
| status | varchar(30) | uploaded/validating/awaiting_review/committed/failed/rolled_back |
| total_rows | integer | 总行数 |
| valid_rows | integer | 有效行数 |
| warning_rows | integer | 警告行数 |
| failed_rows | integer | 失败行数 |
| created_by_user_id | uuid FK | 操作人 |
| summary | jsonb | 汇总结果 |
| started_at/finished_at | timestamptz | 处理时间 |

### question_import_rows

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | 行记录 ID |
| batch_id | uuid FK | 导入批次 |
| sheet_name | varchar(100) | 工作表名 |
| row_no | integer | Excel 行号 |
| question_code | varchar(80) nullable | 题号 |
| raw_data | jsonb | 原始数据 |
| normalized_data | jsonb nullable | 转换后数据 |
| status | varchar(30) | valid/warning/failed/committed |
| errors | jsonb nullable | 错误列表 |
| warnings | jsonb nullable | 警告列表 |
| created_question_id | uuid nullable | 成功创建的题目 |
| created_version_id | uuid nullable | 成功创建的版本 |

## 19. question_error_reports：学生勘误单

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid PK | 是 | 勘误 ID |
| question_id | uuid FK | 是 | 题目 |
| question_version_id | uuid FK | 是 | 学生作答时版本 |
| student_id | uuid FK | 是 | 提交学生 |
| answer_record_id | uuid FK nullable | 否 | 相关答题记录 |
| report_type | varchar(40) | 是 | stem/condition/options/answer/explanation/image/tag/other |
| description | text nullable | 否 | 学生说明 |
| suggested_answer | jsonb nullable | 否 | 学生建议答案 |
| affects_scoring_claimed | boolean | 是 | 学生认为是否影响判分 |
| status | varchar(30) | 是 | student_submitted/ai_reviewing/admin_reviewing/corrected/rejected/retired |
| ai_verdict | varchar(30) nullable | 否 | likely_valid/likely_invalid/uncertain |
| ai_confidence | numeric(5,4) nullable | 否 | AI置信度 |
| ai_result | jsonb nullable | 否 | AI独立求解与证据 |
| final_decision | varchar(30) nullable | 否 | 最终结论 |
| resolved_version_id | uuid FK nullable | 否 | 修正后的版本 |
| created_at/resolved_at | timestamptz | 是/否 | 时间 |

同一学生对同一题只允许一条未结束勘误。

## 20. 推荐索引

- `questions(subject_id, base_grade, lifecycle_status)`；
- `question_versions(question_id, publication_status, version_no desc)`；
- `question_versions(review_status, publication_status)`；
- `question_curriculum_mappings(knowledge_point_id, mapping_type, review_status)`；
- `question_curriculum_mappings(textbook_id, curriculum_node_id)`；
- `question_taxonomy_mappings(taxonomy_node_id, review_status)`；
- `question_assets(sha256)`；
- `question_import_rows(batch_id, status)`；
- `question_error_reports(question_id, status)`；
- `question_embeddings` 根据规模建立 HNSW 索引。

## 21. 当前 Excel 模板与 V2 表的映射

| Excel 字段 | V2 目标表 |
|---|---|
| 题目编码 | questions.question_code |
| 科目、年级 | questions.subject_id/base_grade |
| 题型、难度、认知层级、预计用时 | question_versions |
| 题干、解析、常见错误 | question_versions JSONB |
| 选项 A—E | question_options |
| 标准答案 | question_response_fields + question_answer_rules |
| 题干图片、解析图片 | question_assets + question_version_assets |
| 教材、单元、章节、知识点 | question_curriculum_mappings |
| 题型族、题型模板、技能、易错类型 | question_taxonomy_nodes + mappings |
| 来源、版权 | question_sources |
| 审核状态 | question_reviews + question_versions.review_status |
| 版本号 | question_versions.version_no |

## 22. 实施优先级

### P0：导入和可靠判分

1. `questions`；
2. `question_versions`；
3. `question_options`；
4. `question_response_fields`；
5. `question_answer_rules`；
6. `question_assets` 与关系表；
7. `question_import_batches/rows`；
8. 来源版权和审核表。

### P1：教材、题型和推荐

1. 教材知识点映射；
2. 题型分类树及映射；
3. 质量指标；
4. 向量和题目关系。

### P2：勘误闭环

1. 学生勘误；
2. AI复核；
3. 新版本发布；
4. 历史答题重判和掌握度重算。

## 23. 当前状态说明

截至本设计发布时：

- `docs/08` 和 `docs/09` 已覆盖勘误、推荐、导入、媒体与答案归一化需求；
- 当前 `backend/app/models.py` 仍是 7 张 MVP 简化表；
- 尚未创建 Alembic 迁移；
- 尚未开发 Excel 导入、媒体迁移和数学等价判分代码；
- V2 结构是后续数据库升级与 Excel 模板升级的正式依据。
