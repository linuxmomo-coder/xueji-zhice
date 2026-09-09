# 学迹智评本地资产交接（2026-09-09）

本目录用于把 ChatGPT 工作环境中仍留存的项目本地资产交给后续开发工具。当前代码基线仍以仓库 `main` 为准；本目录中的旧版本压缩包、Demo、PRD、评审、题库模板、费用测算和界面图片仅作为历史资料/产品资料，不应覆盖 `main` 的 v0.3.0 代码。

## 交接包

完整本地资产被打包为：

`xueji-zhice-local-handoff-20260909.zip`

SHA256：

`5da1da06332239a7f763f009b1a0e157937d8c54361b7a23adeb7dcda8eefad0`

由于 GitHub 连接器当前只能写 UTF-8 文本，二进制 ZIP 以 Base64 分片保存：

`xueji-zhice-local-handoff-20260909.zip.b64.part-000` ... `part-019`

### Linux/macOS 还原

```bash
cat xueji-zhice-local-handoff-20260909.zip.b64.part-* > handoff.b64
base64 -d handoff.b64 > xueji-zhice-local-handoff-20260909.zip
sha256sum xueji-zhice-local-handoff-20260909.zip
unzip xueji-zhice-local-handoff-20260909.zip
```

### PowerShell 还原

```powershell
$parts = Get-ChildItem 'xueji-zhice-local-handoff-20260909.zip.b64.part-*' | Sort-Object Name
$b64 = ($parts | ForEach-Object { Get-Content $_ -Raw }) -join ''
[IO.File]::WriteAllBytes('xueji-zhice-local-handoff-20260909.zip',[Convert]::FromBase64String($b64))
Get-FileHash 'xueji-zhice-local-handoff-20260909.zip' -Algorithm SHA256
Expand-Archive 'xueji-zhice-local-handoff-20260909.zip' -DestinationPath './local-handoff'
```

## 内容

详见 `HANDOFF_LOCAL_ASSETS_MANIFEST.txt`。共 24 个项目相关文件，包括 PRD、代码评审、旧版本完整包、题库模板/样例、运营费用表、多个历史 Demo、架构图/界面图、pytest 日志和旧版本说明。

## 后续工具接手建议

1. 先 clone 当前仓库并以 `main` 为代码基线；
2. 解码本交接包作为参考资料；
3. 不要把 v0.2.x 压缩包直接覆盖 v0.3.0；
4. 当前下一开发目标是后台配置中心，优先 PR11-1 AI 模型配置；
5. 每个开发任务以代码提交、PR、CI 通过并合并 `main` 为完成标准。
