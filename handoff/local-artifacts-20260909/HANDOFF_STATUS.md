# 交接状态（2026-09-09）

## 当前代码基线

- 仓库：`linuxmomo-coder/xueji-zhice`
- 默认分支：`main`
- main commit：`c6ec116f8f545ce35afd37e67aacd82f68cf4f1b`
- 当前版本：v0.3.0 production candidate

## 本次交接分支

`handoff/local-artifacts-20260909`

该分支只用于交接本地遗留资料，不应直接作为新的开发基线覆盖 `main`。

## 已实际上传到 GitHub 的交接内容

- `README_HANDOFF.md`
- `HANDOFF_LOCAL_ASSETS_MANIFEST.txt`
- `VISUAL_ASSET_INDEX.md`
- `text-exports/学迹智评_产品需求文档_PRD_v1.0.docx.txt`
- `text-exports/学迹智评_代码全面评审与改进建议.docx.txt`

## 本地完整交接包

ChatGPT 工作环境中已将 24 个项目相关本地文件打包为：

`xueji-zhice-local-handoff-20260909.zip`

SHA256：`5da1da06332239a7f763f009b1a0e157937d8c54361b7a23adeb7dcda8eefad0`

包含旧版完整代码包、PRD、代码评审、题库模板和样例、费用测算、历史 Demo、界面/架构图片、pytest 日志和旧版发布说明。完整文件清单及每个文件 SHA256 见 manifest。

## 重要限制

当前 GitHub 连接器的仓库写入接口只接受 UTF-8 文本内容，没有可把本地二进制文件路径直接作为上传参数的接口。因此 DOCX/XLSX/PNG/ZIP 的二进制原件未伪装成“已上传”。后续接手工具如具备普通 git/gh 或文件上传能力，应优先把完整交接 ZIP 解压后按需纳入仓库或外部制品存储。

## 下一开发任务

建议从 `main` 创建新开发分支，继续：

`PR11-1：AI 模型配置中心`

验收仍应坚持：代码实现 → commit → PR → CI 通过 → merge main。
