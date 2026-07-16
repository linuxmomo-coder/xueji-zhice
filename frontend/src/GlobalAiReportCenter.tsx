import { CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import { api, AuthData, getStoredAuth } from "./api";

type Student = {
  id: string;
  nickname: string;
  current_grade: number;
};

type Policy = {
  terms_version: string;
  privacy_version: string;
  child_policy_version: string;
  required_scope: Record<string, boolean>;
};

type ReportItem = {
  statement: string;
  confidence: "fact" | "high_confidence" | "possible" | "insufficient_data";
  evidence_ids: string[];
};

type ReportAction = {
  title: string;
  reason: string;
  priority: "high" | "medium" | "low";
  evidence_ids: string[];
};

type AIReport = {
  id: string;
  student_id: string;
  report_type: "student_report" | "parent_report";
  status: string;
  provider: string;
  model: string;
  prompt_version: string;
  metrics: Record<string, unknown>;
  evidence_snapshot: {
    generated_at?: string;
    data_window_days?: number;
    evidence?: { id: string; kind: string; data: Record<string, unknown> }[];
  };
  output_json: {
    summary?: string;
    evidence_overview?: ReportItem[];
    strengths?: ReportItem[];
    improvements?: ReportItem[];
    actions?: ReportAction[];
    limitations?: string[];
  };
  usage_json: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
};

const panelStyle: CSSProperties = {
  position: "fixed",
  left: 24,
  bottom: 176,
  width: "min(800px, calc(100vw - 32px))",
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

const confidenceText: Record<ReportItem["confidence"], string> = {
  fact: "事实",
  high_confidence: "较高可信",
  possible: "可能",
  insufficient_data: "数据不足"
};

function ReportItems({ title, items }: { title: string; items?: ReportItem[] }) {
  if (!items?.length) return null;
  return (
    <section style={{ marginTop: 14 }}>
      <h4>{title}</h4>
      {items.map((item, index) => (
        <article key={`${title}-${index}`} style={cardStyle}>
          <b>{item.statement}</b>
          <div style={{ marginTop: 6, color: "#647089" }}>
            可信度：{confidenceText[item.confidence]} · 证据：{item.evidence_ids.join("、") || "无"}
          </div>
        </article>
      ))}
    </section>
  );
}

export default function GlobalAiReportCenter() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [reportType, setReportType] = useState<"student_report" | "parent_report">("student_report");
  const [reports, setReports] = useState<AIReport[]>([]);
  const [selectedReportId, setSelectedReportId] = useState("");

  useEffect(() => {
    const sync = () => setAuth(getStoredAuth());
    window.addEventListener("xueji-auth-updated", sync);
    window.addEventListener("xueji-auth-expired", sync);
    return () => {
      window.removeEventListener("xueji-auth-updated", sync);
      window.removeEventListener("xueji-auth-expired", sync);
    };
  }, []);

  useEffect(() => {
    if (auth?.user.role === "student") setReportType("student_report");
  }, [auth?.user.role]);

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedReportId) ?? reports[0] ?? null,
    [reports, selectedReportId]
  );

  const loadStudents = useCallback(async () => {
    if (!auth || auth.user.role === "admin") return;
    const response = await api<Student[]>("/students?page=1&page_size=100", {}, auth);
    setStudents(response.data);
    setSelectedStudentId((current) =>
      response.data.some((student) => student.id === current)
        ? current
        : response.data[0]?.id ?? ""
    );
  }, [auth]);

  const loadReports = useCallback(async () => {
    if (!auth || !selectedStudentId) {
      setReports([]);
      return;
    }
    const response = await api<AIReport[]>(
      `/students/${selectedStudentId}/ai-reports?page_size=50`,
      {},
      auth
    );
    setReports(response.data);
    setSelectedReportId((current) =>
      response.data.some((report) => report.id === current)
        ? current
        : response.data[0]?.id ?? ""
    );
  }, [auth, selectedStudentId]);

  const loadAll = useCallback(async () => {
    if (!auth || auth.user.role === "admin") return;
    setBusy(true);
    setMessage("");
    try {
      await loadStudents();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "学生档案加载失败");
    } finally {
      setBusy(false);
    }
  }, [auth, loadStudents]);

  useEffect(() => {
    if (open) void loadAll();
  }, [open, loadAll]);

  useEffect(() => {
    if (open) void loadReports();
  }, [open, loadReports]);

  useEffect(() => {
    if (!open || !reports.some((report) => ["queued", "running", "retrying"].includes(report.status))) {
      return;
    }
    const timer = window.setInterval(() => void loadReports(), 5000);
    return () => window.clearInterval(timer);
  }, [open, reports, loadReports]);

  async function authorizeAutomatedAnalysis() {
    if (!auth || auth.user.role !== "parent") return;
    setBusy(true);
    setMessage("");
    try {
      const policy = await api<Policy>("/legal/current", {}, null);
      await api(
        "/legal/consents",
        {
          method: "POST",
          body: JSON.stringify({
            terms_version: policy.data.terms_version,
            privacy_version: policy.data.privacy_version,
            child_policy_version: policy.data.child_policy_version,
            consent_scope: {
              ...policy.data.required_scope,
              automated_analysis: true
            }
          })
        },
        auth
      );
      setMessage("已记录自动学习分析授权，可以生成基于真实证据的AI报告。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "授权提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function createReport() {
    if (!auth || !selectedStudentId) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await api<AIReport>(
        "/ai-reports",
        {
          method: "POST",
          body: JSON.stringify({ student_id: selectedStudentId, report_type: reportType })
        },
        auth
      );
      setSelectedReportId(response.data.id);
      setMessage("报告任务已进入队列。报告生成期间不会使用未确认资料。 ");
      await loadReports();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告生成请求失败");
    } finally {
      setBusy(false);
    }
  }

  async function retryReport(report: AIReport) {
    if (!auth) return;
    setBusy(true);
    setMessage("");
    try {
      await api(`/ai-reports/${report.id}/retry`, { method: "POST" }, auth);
      setMessage("失败报告已重新进入队列。");
      await loadReports();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告重试失败");
    } finally {
      setBusy(false);
    }
  }

  if (!auth || auth.user.role === "admin") return null;
  const evidence = selectedReport?.evidence_snapshot.evidence ?? [];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        style={{
          ...buttonStyle,
          position: "fixed",
          left: 24,
          bottom: 126,
          background: "#8a3f75",
          color: "#fff",
          zIndex: 1001
        }}
      >
        AI学习报告
      </button>
      {open && (
        <aside style={panelStyle} aria-label="AI学习报告中心">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div>
              <strong style={{ fontSize: 20 }}>AI学习报告</strong>
              <div style={{ color: "#647089" }}>所有结论必须引用冻结的真实证据ID</div>
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

          <section style={{ marginTop: 18, display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 10, alignItems: "end" }}>
            <label style={{ display: "grid", gap: 6 }}>
              学生
              <select value={selectedStudentId} onChange={(event) => setSelectedStudentId(event.target.value)} style={inputStyle}>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.nickname} · {student.current_grade}年级
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              报告类型
              <select
                value={reportType}
                disabled={auth.user.role === "student"}
                onChange={(event) => setReportType(event.target.value as "student_report" | "parent_report")}
                style={inputStyle}
              >
                <option value="student_report">学生版</option>
                {auth.user.role === "parent" && <option value="parent_report">家长版</option>}
              </select>
            </label>
            <button
              type="button"
              disabled={busy || !selectedStudentId}
              onClick={() => void createReport()}
              style={{ ...buttonStyle, background: "#8a3f75", color: "#fff" }}
            >
              生成报告
            </button>
          </section>

          {auth.user.role === "parent" && (
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                disabled={busy}
                onClick={() => void authorizeAutomatedAnalysis()}
                style={{ ...buttonStyle, background: "#eef1f7" }}
              >
                授权自动学习分析
              </button>
              <small style={{ marginLeft: 8 }}>未授权时系统会拒绝生成AI报告。</small>
            </div>
          )}

          <section style={{ marginTop: 18, display: "grid", gridTemplateColumns: "minmax(220px, .8fr) minmax(360px, 1.6fr)", gap: 14 }}>
            <div>
              <h3>报告记录</h3>
              {reports.length ? reports.map((report) => (
                <button
                  type="button"
                  key={report.id}
                  onClick={() => setSelectedReportId(report.id)}
                  style={{
                    ...cardStyle,
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    background: report.id === selectedReport?.id ? "#f4eaf2" : "#fff",
                    cursor: "pointer"
                  }}
                >
                  <b>{report.report_type === "parent_report" ? "家长版" : "学生版"}</b>
                  <div>状态：{report.status}</div>
                  <small>{new Date(report.created_at).toLocaleString("zh-CN")}</small>
                </button>
              )) : <p>暂无AI报告。</p>}
            </div>

            <div>
              {selectedReport ? (
                <article style={cardStyle}>
                  <h3 style={{ marginTop: 0 }}>
                    {selectedReport.report_type === "parent_report" ? "家长版报告" : "学生版报告"}
                  </h3>
                  <p>
                    状态：<b>{selectedReport.status}</b> · 提供方：{selectedReport.provider} · 模型：{selectedReport.model}
                  </p>
                  <p>提示词版本：{selectedReport.prompt_version}</p>
                  {selectedReport.error_message && (
                    <p style={{ color: "#a22" }}>
                      {selectedReport.error_code}：{selectedReport.error_message}
                    </p>
                  )}
                  {selectedReport.status === "failed" && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void retryReport(selectedReport)}
                      style={{ ...buttonStyle, background: "#a44b00", color: "#fff" }}
                    >
                      重试生成
                    </button>
                  )}
                  {selectedReport.status === "completed" && (
                    <>
                      <p style={{ fontSize: 17, lineHeight: 1.6 }}>{selectedReport.output_json.summary}</p>
                      <ReportItems title="证据概览" items={selectedReport.output_json.evidence_overview} />
                      <ReportItems title="当前优势" items={selectedReport.output_json.strengths} />
                      <ReportItems title="需要巩固" items={selectedReport.output_json.improvements} />
                      {selectedReport.output_json.actions?.length ? (
                        <section style={{ marginTop: 14 }}>
                          <h4>建议行动</h4>
                          {selectedReport.output_json.actions.map((action, index) => (
                            <article key={`action-${index}`} style={cardStyle}>
                              <b>{action.title} · {action.priority}</b>
                              <p>{action.reason}</p>
                              <small>证据：{action.evidence_ids.join("、")}</small>
                            </article>
                          ))}
                        </section>
                      ) : null}
                      {selectedReport.output_json.limitations?.length ? (
                        <section style={{ marginTop: 14 }}>
                          <h4>报告局限</h4>
                          <ul>{selectedReport.output_json.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
                        </section>
                      ) : null}
                      <details style={{ marginTop: 14 }}>
                        <summary style={{ cursor: "pointer" }}>查看证据快照与用量</summary>
                        <p>证据生成时间：{selectedReport.evidence_snapshot.generated_at || "未记录"}</p>
                        {evidence.map((item) => (
                          <article key={item.id} style={cardStyle}>
                            <b>{item.id}</b> · {item.kind}
                            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{JSON.stringify(item.data, null, 2)}</pre>
                          </article>
                        ))}
                        <pre style={{ whiteSpace: "pre-wrap" }}>Token用量：{JSON.stringify(selectedReport.usage_json, null, 2)}</pre>
                      </details>
                    </>
                  )}
                </article>
              ) : (
                <p>选择一份报告查看详细内容。</p>
              )}
            </div>
          </section>
        </aside>
      )}
    </>
  );
}
