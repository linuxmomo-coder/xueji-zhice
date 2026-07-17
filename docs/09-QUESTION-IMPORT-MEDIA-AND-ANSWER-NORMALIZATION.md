# 题库导入、媒体存储与答案归一化设计

## 1. Excel导入

导入模式：`validate_only/staging/commit/rollback/upsert`。流程：上传→字段和JSON校验→代码映射→媒体迁移→暂存→人工审核→事务提交→结果报告。按`question_code`升级版本，禁止静默覆盖。

建议表：`question_import_batches`和`question_import_rows`，保存文件摘要、行号、原始/标准化数据、错误、警告和生成ID。

## 2. 媒体

图片、音频和附件必须进入项目自有MinIO/COS；数据库保存稳定`asset_id/object_key/sha256/MIME/尺寸/来源`。外链只追溯，不能作为前端长期展示地址。SVG必须清洗；下载验证真实MIME、大小、摘要、重定向和域名白名单。

## 3. 答案归一化

通用顺序：Unicode NFKC→清理空白和零宽字符→全角转半角→统一负号/括号/标点→按题目配置大小写→保留原始值和归一化值。

数学输入支持：`√3/sqrt(3)/\sqrt{3}`、`×/*/·`、`÷//`、`x²/x^2`、`π/pi`、比例和单位。禁止字符串直接比较和Python eval。

## 4. 多空与多答案

每个空建立独立`question_response_field`和`question_answer_rule`，配置顺序、单位、误差、大小写、分数小数等价和解析失败策略。

## 5. 当前20题导入包

可作为staging输入；发布前必须完成版权审核、知识点/教材ID映射和题图迁移。`pending_review`题目不得进入学生练习。
