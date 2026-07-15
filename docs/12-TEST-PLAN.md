# 学迹智评测试计划 v0.2

## 1. 质量门禁

Pull Request必须通过：

- `pytest --cov=app --cov-fail-under=60`；
- Ruff静态检查；
- Bandit安全扫描；
- Alembic空库upgrade和downgrade演练；
- TypeScript检查和Vite构建；
- Docker Compose解析；
- 前后端镜像构建。

## 2. 已实现后端用例

| 范围 | 用例 |
|---|---|
| 健康/配置 | health；production弱密钥、demo、SQLite、CORS拒绝 |
| 认证 | 家长注册、登录、refresh轮换、logout |
| 家庭隔离 | 家庭A不能读取家庭B学生；未登录不能访问 |
| 学生 | 创建、分页、详情与角色限制 |
| 题库 | 只选择active且approved/published版本 |
| 练习 | 创建session、快照、next不泄露答案、首次提交 |
| 判分 | 选择集合、NFKC、大小写、数值容差、根式等价 |
| 错题 | 错答创建/累计wrong_question |
| 文件 | MIME/大小/摘要/重复/确认权限（需继续扩充） |

## 3. 测试数据

测试使用临时SQLite和显式fixture，不自动加载开发seed。测试账号和题目均为虚构数据；每个测试独立事务/数据库文件。

## 4. 前端测试计划

下一阶段增加：

- Vitest：错误映射、token存储、导航权限、loading和空状态；
- Playwright路径A：家长注册→创建学生→上传资料→确认；
- Playwright路径B：学生登录→练习→错答→错题→复测；
- 无障碍：键盘、focus-visible、ARIA、对比度和移动触控目标。

## 5. 安全测试

- 401/403矩阵和IDOR；
- JWT类型、过期、签名和撤销；
- 文件路径穿越、伪MIME、超限、重复和SVG；
- 数学表达式拒绝属性、函数注入和超复杂表达式；
- 密钥扫描、依赖漏洞和镜像扫描；
- 日志敏感数据检查。

## 6. 上线验收

1. 未登录无法读取学生数据；
2. 跨家庭访问全部403；
3. production弱配置启动失败；
4. production不存在demo路由和seed；
5. 空库能迁移到head；
6. 练习保存版本快照，题库更新不改历史；
7. 全角、根号和等价表达式正确判分；
8. 错答生成错题；
9. 文件不经Nginx公开；
10. CI全绿且部署后health通过。
