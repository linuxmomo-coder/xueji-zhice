# 题库数据库结构 V2

## 1. 正式结构

```text
questions
└─ question_versions
   ├─ question_options
   ├─ question_response_fields ─ question_answer_rules
   ├─ question_version_assets ─ question_assets
   ├─ question_curriculum_mappings
   ├─ question_taxonomy_mappings
   ├─ question_reviews
   └─ question_embeddings
questions ─ question_sources / quality_metrics / relations / error_reports
question_import_batches ─ question_import_rows
```

## 2. 当前v0.2已落地

`questions, question_versions, question_options, question_response_fields, question_answer_rules, question_assets, question_version_assets`以及练习快照和判分引用。内容版本发布后不静默覆盖。

## 3. 下一阶段

补充来源版权、细分审核、教材知识点多对多映射、题型分类、质量指标、向量、显式相似/变式关系、导入批次、勘误和重判任务。

## 4. 核心约束

- question_code全库唯一；
- `(question_id,version_no)`唯一；
- active题必须指向approved/published版本；
- 必需媒体缺失不得发布；
- 正确选项和填空答案统一由规则表管理；
- 历史PracticeItem保存版本ID和快照；
- 高风险争议题使用suspended而不是删除。

详细字段以docs/04和Alembic模型为当前事实基线；本文件描述完整目标模型。
