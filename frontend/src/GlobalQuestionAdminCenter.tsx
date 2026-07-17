import { CSSProperties, FormEvent, useCallback, useEffect, useState } from "react";
import { api, AuthData, getStoredAuth } from "./api";

type ImportBatch = {
  id: string;
  file_name: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  warning_rows: number;
  failed_rows: number;
  committed_rows: number;
  created_at: string;
};

type ImportRow = {
  id: string;
  row_number: number;
  question_code: string | null;
  errors: string[];
  warnings: string[];
  status: string;
};

type Version = {
  id: string;
  question_id: string;
  question_code: string;
  subject: string;
  grade: number;
  version_no: number;
  display_type: string;
  stem_content: { blocks?: { type: string; value?: string }[] };
  answer_summary: string | null;
  review_status: string;
  publication_status: string;
  source: {
    copyright_status: string;
    review_status: string;
    source_name: string | null;
    source_url: string | null;
    metadata: { external_image_urls?: string[] } | null;
  } | null;
};

const panelStyle: CSSProperties = {
  position: "fixed",
  right: 24,
  bottom: 126,
  width: "min(760px, calc(100vw - 32px))",
  maxHeight: "82vh",
  overflowY: "auto",
  background: "#fff",
  border: "1px solid #dce3f0",
  borderRadius: 18,
  boxShadow: "0 18px 60px rgba(20, 32, 70, .24)",
  padding: 20,
  zIndex: 1000
};
const buttonStyle: CSSProperties = { border: 0, borderRadius: 10, padding: "9px 13px", cursor: "pointer" };
const cardStyle: CSSProperties = { border: "1px solid #e1e6f0", borderRadius: 12, padding: 12, marginBottom: 10 };

function stemText(version: Version): string {
  return (version.stem_content?.blocks ?? []).map((block) => block.value ?? "").join(" ").trim();
}

export default function GlobalQuestionAdminCenter() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<ImportBatch | null>(null);
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [assetIds, setAssetIds] = useState<Record<string, string>>({});

  useEffect(() => {
    const sync = () => setAuth(getStoredAuth());
    window.addEventListener("xueji-auth-updated", sync);
    window.addEventListener("xueji-auth-expired", sync);
    return () => {
      window.removeEventListener("xueji-auth-updated", sync);
      window.removeEventListener("xueji-auth-expired", sync);
    };
  }, []);

  const load = useCallback(async () => {
    if (!auth || auth.user.role !== "admin") return;
    setBusy(true);
    try {
      const [batchResponse, versionResponse] = await Promise.all([
        api<ImportBatch[]>("/admin/question-imports?page_size=100", {}, auth),
        api<Version[]>("/admin/question-versions?review_status=pending_review", {}, auth)
      ]);
      setBatches(batchResponse.data);
      setVersions(versionResponse.data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "题库管理数据加载失败");
    } finally {
      setBusy(false);
    }
  }, [auth]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function uploadImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setMessage("");
    try {
      const response = await api<ImportBatch>(
        "/admin/question-imports/upload",
        { method: "POST", body: form },
        auth
      );
      setMessage(`校验完成：有效 ${response.data.valid_rows} 行，错误 ${response.data.failed_rows} 行。`);
      event.currentTarget.reset();
      await load();
      await viewBatch(response.data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "题库文件上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function viewBatch(batch: ImportBatch) {
    if (!auth) return;
    setSelectedBatch(batch);
    try {
      const response = await api<{ batch: ImportBatch; rows: ImportRow[] }>(
        `/admin/question-imports/${batch.id}`,
        {},
        auth
      );
      setSelectedBatch(response.data.batch);
      setRows(response.data.rows);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导入明细加载失败");
    }
  }

  async function commitBatch(batchId: string) {
    if (!auth) return;
    setBusy(true);
    try {
      const response = await api<ImportBatch>(
        `/admin/question-imports/${batchId}/commit`,
        { method: "POST" },
        auth
      );
      setMessage(`已创建 ${response.data.committed_rows} 个待审核题目版本。`);
      await load();
      await viewBatch(response.data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提交导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function review(version: Version, decision: "approved" | "rejected" | "changes_requested") {
    if (!auth) return;
    setBusy(true);
    try {
      await api(
        `/admin/question-versions/${version.id}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            review_type: "full",
            comment: decision === "approved" ? "管理员确认题干、答案、解析和版权来源" : "需要修订",
            source_review_status: decision === "approved" ? "approved" : decision === "rejected" ? "rejected" : "pending"
          })
        },
        auth
      );
      setMessage(`${version.question_code} 已完成审核。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审核失败");
    } finally {
      setBusy(false);
    }
  }

  async function publish(version: Version) {
    if (!auth) return;
    setBusy(true);
    try {
      await api(
        `/admin/question-versions/${version.id}/publish`,
        { method: "POST", body: JSON.stringify({ change_summary: "管理员审核发布" }) },
        auth
      );
      setMessage(`${version.question_code} 已发布。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadAndLinkAsset(event: FormEvent<HTMLFormElement>, version: Version) {
    event.preventDefault();
    if (!auth) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const asset = await api<{ id: string }>(
        "/admin/question-assets",
        { method: "POST", body: form },
        auth
      );
      await api(
        `/admin/question-versions/${version.id}/assets`,
        {
          method: "POST",
          body: JSON.stringify({ asset_id: asset.data.id, asset_role: "stem", is_required: true })
        },
        auth
      );
      setAssetIds((current) => ({ ...current, [version.id]: asset.data.id }));
      setMessage(`${version.question_code} 的题图已迁移并关联。`);
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "题图迁移失败");
    } finally {
      setBusy(false);
    }
  }

  if (!auth || auth.user.role !== "admin") return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        style={{ ...buttonStyle, position: "fixed", right: 24, bottom: 76, background: "#096b61", color: "#fff", zIndex: 1001 }}
      >
        题库导入与审核
      </button>
      {open && (
        <aside style={panelStyle} aria-label="题库导入与审核工作台">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div><strong style={{ fontSize: 20 }}>题库导入与审核</strong><div style={{ color: "#647089" }}>Excel只进入草稿区，审核后才可发布</div></div>
            <button type="button" onClick={() => setOpen(false)} style={{ ...buttonStyle, background: "#eef1f7" }}>关闭</button>
          </div>
          {message && <p style={{ background: "#eef4ff", borderRadius: 10, padding: 10 }}>{message}</p>}

          <section style={{ marginTop: 18 }}>
            <h3>1. 上传并校验Excel</h3>
            <form onSubmit={uploadImport} style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <input name="file" type="file" accept=".xlsx" required />
              <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#096b61", color: "#fff" }}>上传校验</button>
            </form>
          </section>

          <section style={{ marginTop: 18 }}>
            <h3>2. 导入批次</h3>
            {batches.length ? batches.map((batch) => (
              <article key={batch.id} style={cardStyle}>
                <b>{batch.file_name}</b> <small>{new Date(batch.created_at).toLocaleString("zh-CN")}</small>
                <div>状态：{batch.status} · 总行 {batch.total_rows} · 有效 {batch.valid_rows} · 警告 {batch.warning_rows} · 错误 {batch.failed_rows} · 已提交 {batch.committed_rows}</div>
                <button type="button" onClick={() => void viewBatch(batch)} style={{ ...buttonStyle, marginTop: 8, background: "#eef1f7" }}>查看明细</button>
                {batch.status.startsWith("validated") && <button type="button" disabled={busy} onClick={() => void commitBatch(batch.id)} style={{ ...buttonStyle, marginLeft: 8, background: "#253a84", color: "#fff" }}>提交无错误行</button>}
              </article>
            )) : <p>暂无导入批次。</p>}
          </section>

          {selectedBatch && (
            <section style={{ marginTop: 18 }}>
              <h3>批次明细：{selectedBatch.file_name}</h3>
              <div style={{ maxHeight: 230, overflowY: "auto" }}>
                {rows.map((row) => (
                  <article key={row.id} style={cardStyle}>
                    <b>第 {row.row_number} 行 · {row.question_code || "无题号"}</b> · {row.status}
                    {row.errors.length > 0 && <div style={{ color: "#a22" }}>错误：{row.errors.join("；")}</div>}
                    {row.warnings.length > 0 && <div style={{ color: "#9a5a00" }}>警告：{row.warnings.join("；")}</div>}
                  </article>
                ))}
              </div>
            </section>
          )}

          <section style={{ marginTop: 18 }}>
            <h3>3. 待审核题目版本</h3>
            {versions.length ? versions.map((version) => {
              const externalImages = version.source?.metadata?.external_image_urls ?? [];
              return (
                <article key={version.id} style={cardStyle}>
                  <b>{version.question_code} · v{version.version_no}</b>
                  <div>{version.subject} · {version.grade}年级 · {version.display_type}</div>
                  <p>{stemText(version)}</p>
                  <div>答案：{version.answer_summary || "未提供"}</div>
                  <div>版权：{version.source?.copyright_status || "未记录"} · 来源审核：{version.source?.review_status || "未审核"}</div>
                  {externalImages.length > 0 && <div style={{ color: "#9a5a00" }}>存在外部题图，必须上传到自有存储后才能发布。</div>}
                  {externalImages.length > 0 && !assetIds[version.id] && (
                    <form onSubmit={(event) => void uploadAndLinkAsset(event, version)} style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      <input name="file" type="file" accept="image/png,image/jpeg,image/webp" required />
                      <input name="alt_text" placeholder="题图说明" />
                      <input name="source_url" type="hidden" value={externalImages[0]} />
                      <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#eef1f7" }}>迁移并关联题图</button>
                    </form>
                  )}
                  <div style={{ marginTop: 10 }}>
                    <button type="button" disabled={busy} onClick={() => void review(version, "approved")} style={{ ...buttonStyle, background: "#096b61", color: "#fff" }}>审核通过</button>
                    <button type="button" disabled={busy} onClick={() => void review(version, "changes_requested")} style={{ ...buttonStyle, marginLeft: 8, background: "#f4e8ce" }}>要求修改</button>
                    <button type="button" disabled={busy} onClick={() => void review(version, "rejected")} style={{ ...buttonStyle, marginLeft: 8, background: "#f8dddd" }}>拒绝</button>
                    {version.review_status === "approved" && <button type="button" disabled={busy} onClick={() => void publish(version)} style={{ ...buttonStyle, marginLeft: 8, background: "#253a84", color: "#fff" }}>发布</button>}
                  </div>
                </article>
              );
            }) : <p>暂无待审核题目。</p>}
          </section>
        </aside>
      )}
    </>
  );
}
