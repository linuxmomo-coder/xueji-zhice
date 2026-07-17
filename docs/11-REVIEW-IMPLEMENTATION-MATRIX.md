# 代码评审建议落实矩阵

## 1. 版本范围

基于《学迹智评_代码全面评审与改进建议》形成v0.2.0交付。矩阵区分“已实现”“部分实现”“后续计划”，避免文档超前于代码。

## 2. P0

| 编号 | 评审问题 | 本版本措施 | 状态 | 验证 |
|---|---|---|---|---|
| P0-01 | 角色切换不是权限 | User/Family/Member/Session；JWT；统一student policy；前端移除角色切换 | 已实现 | 未登录401、跨家庭403测试 |
| P0-02 | demo与生产混用 | DemoRouter条件注册；seed双开关；production禁止 | 已实现 | 配置测试、OpenAPI检查 |
| P0-03 | 默认密钥和密码 | production fail-fast；强密钥、非SQLite、无通配CORS | 已实现 | 启动配置单测 |
| P0-04 | create_all替代迁移 | Alembic初始迁移；生产入口upgrade head | 已实现 | CI升降级演练 |

## 3. P1

| 建议 | 落实 | 状态 |
|---|---|---|
| Service/Repository层 | auth、practice、grading、storage及核心repository分层 | 已实现基础 |
| 分页和错误协议 | students/questions分页；统一error+request_id | 已实现 |
| 作答判题闭环 | PracticeItem快照、Attempt、WrongQuestion | 已实现首条闭环 |
| 上传链路 | MIME/大小/SHA256/私有目录/重复检查/确认审计 | 已实现基础；病毒扫描和对象存储待接 |
| 主键关系和审计 | created_by、family范围、AuditEvent | 部分实现 |
| 任务型UI | 登录身份、导航、操作反馈、无原始JSON | 已实现 |
| 测试 | 认证隔离、配置、练习和判分；覆盖率门禁 | 已实现基线 |
| 前端测试/E2E | Vitest/Playwright | 后续计划 |

## 4. 架构建议

模块化单体保留，未过早拆微服务。Redis、OCR、LLM和对象存储通过适配器/配置预留；耗时任务将在下一版进入队列。

## 5. 仍需完成

1. 真实对象存储和恶意文件扫描；
2. Excel题库导入、后台审核和版权工作台；
3. 教材知识点、题型树与相似题推荐；
4. OCR和AI异步任务；
5. 前端单测和两条Playwright E2E；
6. 数据导出、删除、通知和完整审计；
7. 可观测性、告警与恢复演练。
