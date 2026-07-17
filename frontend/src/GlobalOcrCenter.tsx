import { CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import { api, apiBlob, AuthData, getStoredAuth } from "./api";

type Student = {
  id: string;
  nickname: string;
  current_grade: number;
};

type DocumentRecord = {
  id: string;
  document_type: string;
  file_name: string;
  status: string;
  structured_data: Record<string, unknown> | null;
  confirmed_data: Record<string, unknown> | null;
  created_at: string;
};

type OcrJob = {
  id: string;
  provider: string;
  status: string;
  attempts: number;
  max_attempts: number;
  error_code: string | null;
  error_message: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  next_retry_at: string | null;
};

type OcrStatus = {
  document_id: string;
  document_status: string;
  job: OcrJob | null;
};

const panelStyle: CSSProperties = {
  position: "fixed",
  left: 24,
  bottom: 126,
  width: "min(720px, calc(100vw - 32px))",
  maxHeight: "82vh",
  overflowY: "auto",
  background: "#fff",
  border: "1px solid #dce3f0",
  borderRadius: 18,
  boxShadow: "0 18px 60px rgba(20, 32, 70, .24)",
  padding: 20,
  zIndex: 1000
};
const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: 10,
  padding: "9px 13px",
  cursor: "pointer"
};
const cardStyle: CSSProperties = {
  border: "1px solid #e1e6f0",
  borderRadius: 12,
  padding: 12,
  marginBottom: 10
};
const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  border: "1px solid #cfd7e6",
  borderRadius: 10,
  padding: "10px 12px"
};

const statusText: Record<string, string> = {
  uploaded: "文件已上传",
  ocr_queued: "等待OCR识别",
  ocr_processing: "OCR识别中",
  ocr_failed: "OCR识别失败",
  awaiting_confirmation: "等待家长确认",
  confirmed: "已确认入档"
};

function confidenceOf(document: DocumentRecord): number | null {
  const raw = document.structured_data?.mean_confidence;
  return typeof raw === "number" ? raw : null;
}

function initialDraft(document: DocumentRecord): string {
  const structured = document.confirmed_data ?? document.structured_data;
  if (!structured) return "{}";
  const extracted = structured.extracted;
  return JSON.stringify(
    typeof extracted === "object" && extracted !== null ? extracted : structured,
    null,
    2
  );
}

export default function GlobalOcrCenter() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [ocrStatus, setOcrStatus] = useState<OcrStatus | null>(null);
  const [draft, setDraft] = useState("{}");

  useEffect(() => {
    const sync = () => setAuth(getStoredAuth());
    window.addEventListener("xueji-auth-updated", sync);
    window.addEventListener("xueji-auth-expired", sync);
    return () => {
      window.removeEventListener("xueji-auth-updated", sync);
      window.removeEventListener("xueji-auth-expired", sync);
    };
  }, []);

  const selectedDocument = useMemo(
    () => documents.find((item) => item.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  );

  const loadStudents = useCallback(async () => {
    if (!auth || auth.user.role === "admin") return;
    const response = await api<Student[]>("/students?page=1&page_size=100", {}, auth);
    setStudents(response.data);
    setSelectedStudentId((current) =>
      response.data.some((item) => item.id === current)
        ? current
        : response.data[0]?.id ?? ""
    );
  }, [auth]);

  const loadDocuments = useCallback(async () => {
    if (!auth || !selectedStudentId) {
      setDocuments([]);
      setSelectedDocumentId("");
      return;
    }
    const response = await api<DocumentRecord[]>(
      `/documents?student_id=${selectedStudentId}`,
      {},
      auth
    );
    setDocuments(response.data);
    setSelectedDocumentId((current) =>
      response.data.some((item) => item.id === current)
        ? current
        : response.data[0]?.id ?? ""
    );
  }, [auth, selectedStudentId]);

  const loadStatus = useCallback(async () => {
    if (!auth || !selectedDocumentId) {
      setOcrStatus(null);
      return;
    }
    try {
      const response = await api<OcrStatus>(
        `/documents/${selectedDocumentId}/ocr`,
        {},
        auth
      );
      setOcrStatus(response.data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "OCR状态加载失败");
    }
  }, [auth, selectedDocumentId]);

  const loadAll = useCallback(async () => {
    if (!auth || auth.user.role === "admin") return;
    setBusy(true);
    setMessage("");
    try {
      await loadStudents();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "学生资料加载失败");
    } finally {
      setBusy(false);
    }
  }, [auth, loadStudents]);

  useEffect(() => {
    if (open) void loadAll();
  }, [open, loadAll]);

  useEffect(() => {
    if (open) void loadDocuments();
  }, [open, loadDocuments]);

  useEffect(() => {
    if (!selectedDocument) {
      setDraft("{}");
      setOcrStatus(null);
      return;
    }
    setDraft(initialDraft(selectedDocument));
    void loadStatus();
  }, [selectedDocument, loadStatus]);

  useEffect(() => {
    if (!open || !ocrStatus?.job) return;
    if (!["queued", "running", "retrying"].includes(ocrStatus.job.status)) return;
    const timer = window.setInterval(() => {
      void loadStatus();
      void loadDocuments();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [open, ocrStatus?.job, loadStatus, loadDocuments]);

  async function retryOcr() {
    if (!auth || !selectedDocument) return;
    setBusy(true);
    setMessage("");
    try {
      await api(
        `/documents/${selectedDocument.id}/ocr/retry`,
        { method: "POST" },
        auth
      );
      setMessage("OCR重试任务已进入队列。");
      await loadStatus();
      await loadDocuments();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "OCR重试失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDocument() {
    if (!auth || auth.user.role !== "parent" || !selectedDocument) return;
    let confirmedData: Record<string, unknown>;
    try {
      const parsed = JSON.parse(draft) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("确认内容必须为JSON对象");
      }
      confirmedData = parsed as Record<string, unknown>;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认内容不是有效JSON");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await api(
        `/documents/${selectedDocument.id}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({ confirmed_data: confirmedData })
        },
        auth
      );
      setMessage("家长确认已保存，资料已正式入档。");
      await loadDocuments();
      await loadStatus();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "资料确认失败");
    } finally {
      setBusy(false);
    }
  }

  async function openOriginal() {
    if (!auth || !selectedDocument) return;
    setBusy(true);
    try {
      const blob = await apiBlob(`/documents/${selectedDocument.id}/file`, auth);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "原文件打开失败");
    } finally {
      setBusy(false);
    }
  }

  if (!auth || auth.user.role === "admin") return null;
  const confidence = selectedDocument ? confidenceOf(selectedDocument) : null;
  const canRetry = auth.user.role === "parent" && selectedDocument?.status === "ocr_failed";
  const canConfirm = auth.user.role === "parent" && selectedDocument?.status === "awaiting_confirmation";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        style={{
          ...buttonStyle,
          position: "fixed",
          left: 24,
          bottom: 76,
          background: "#4e3f96",
          color: "#fff",
          zIndex: 1001
        }}
      >
        资料识别与确认
      </button>
      {open && (
        <aside style={panelStyle} aria-label="资料识别与确认工作台">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div>
              <strong style={{ fontSize: 20 }}>资料识别与确认</strong>
              <div style={{ color: "#647089" }}>显示真实OCR任务状态，不以演示结果代替识别</div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              style={{ ...buttonStyle, background: "#eef1f7" }}
            >
              关闭
            </button>
          </div>

          {message && (
            <p style={{ background: "#eef4ff", borderRadius: 10, padding: 10 }}>{message}</p>
          )}

          <section style={{ marginTop: 18 }}>
            <label style={{ display: "grid", gap: 6 }}>
              学生
              <select
                value={selectedStudentId}
                onChange={(event) => setSelectedStudentId(event.target.value)}
                style={inputStyle}
              >
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.nickname} · {student.current_grade}年级
                  </option>
                ))}
              </select>
            </label>
          </section>

          <section style={{ marginTop: 18 }}>
            <h3>资料记录</h3>
            {documents.length ? (
              <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) minmax(300px, 1.5fr)", gap: 14 }}>
                <div>
                  {documents.map((document) => (
                    <button
                      type="button"
                      key={document.id}
                      onClick={() => setSelectedDocumentId(document.id)}
                      style={{
                        ...cardStyle,
                        display: "block",
                        width: "100%",
                        textAlign: "left",
                        background: document.id === selectedDocumentId ? "#eef0ff" : "#fff",
                        cursor: "pointer"
                      }}
                    >
                      <b>{document.file_name}</b>
                      <div>{document.document_type} · {statusText[document.status] ?? document.status}</div>
                      <small>{new Date(document.created_at).toLocaleString("zh-CN")}</small>
                    </button>
                  ))}
                </div>

                {selectedDocument && (
                  <div style={cardStyle}>
                    <h3 style={{ marginTop: 0 }}>{selectedDocument.file_name}</h3>
                    <p>
                      状态：<b>{statusText[selectedDocument.status] ?? selectedDocument.status}</b>
                    </p>
                    {ocrStatus?.job && (
                      <div>
                        <p>
                          OCR提供方：{ocrStatus.job.provider} · 任务状态：{ocrStatus.job.status} · 尝试次数：
                          {ocrStatus.job.attempts}/{ocrStatus.job.max_attempts}
                        </p>
                        {ocrStatus.job.error_message && (
                          <p style={{ color: "#a22" }}>
                            {ocrStatus.job.error_code}：{ocrStatus.job.error_message}
                          </p>
                        )}
                      </div>
                    )}
                    {confidence !== null && (
                      <p>
                        平均置信度：<b>{(confidence * 100).toFixed(1)}%</b>
                      </p>
                    )}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void openOriginal()}
                        style={{ ...buttonStyle, background: "#eef1f7" }}
                      >
                        查看原文件
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void loadStatus()}
                        style={{ ...buttonStyle, background: "#eef1f7" }}
                      >
                        刷新状态
                      </button>
                      {canRetry && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void retryOcr()}
                          style={{ ...buttonStyle, background: "#a44b00", color: "#fff" }}
                        >
                          重新识别
                        </button>
                      )}
                    </div>

                    {(canConfirm || selectedDocument.status === "confirmed") && (
                      <section>
                        <h4>结构化数据</h4>
                        <textarea
                          value={draft}
                          onChange={(event) => setDraft(event.target.value)}
                          readOnly={selectedDocument.status === "confirmed" || auth.user.role !== "parent"}
                          rows={12}
                          style={{ ...inputStyle, fontFamily: "ui-monospace, monospace", resize: "vertical" }}
                        />
                        {canConfirm && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void confirmDocument()}
                            style={{ ...buttonStyle, marginTop: 10, background: "#096b61", color: "#fff" }}
                          >
                            家长确认并正式入档
                          </button>
                        )}
                      </section>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p>当前学生暂无上传资料。</p>
            )}
          </section>
        </aside>
      )}
    </>
  );
}
