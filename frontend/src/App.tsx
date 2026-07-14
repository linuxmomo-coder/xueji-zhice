import { useEffect, useMemo, useState } from "react";

type Role = "student" | "parent" | "admin";

type Metric = { label: string; value: string; trend: string };
type Task = { title: string; type: string; minutes: number };
type Notice = { title: string; content: string };
type Dashboard = {
  role: Role;
  profile: { student_id?: string | null; student_name?: string; grade?: number; term?: string };
  metrics: Metric[];
  tasks: Task[];
  notices: Notice[];
};

type ApiResult = Record<string, unknown>;

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

const roleLabels: Record<Role, string> = {
  student: "学生端",
  parent: "家长端",
  admin: "后台管理端"
};

const roleDescriptions: Record<Role, string> = {
  student: "今日任务、本地题库练习、错题复测与学生版AI分析",
  parent: "成绩评语确认、多维分析、学习方案与任务推送",
  admin: "教材知识点、题库、AI/OCR配置与系统运行管理"
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败：${response.status}`);
  }
  return (await response.json()) as T;
}

export default function App() {
  const [role, setRole] = useState<Role>("student");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("正在连接后端……");
  const [result, setResult] = useState<ApiResult | null>(null);

  const accent = useMemo(() => {
    if (role === "parent") return "green";
    if (role === "admin") return "orange";
    return "purple";
  }, [role]);

  useEffect(() => {
    setLoading(true);
    setResult(null);
    api<Dashboard>(`/dashboard/${role}`)
      .then((data) => {
        setDashboard(data);
        setMessage("已连接学迹智评后端服务");
      })
      .catch((error: Error) => setMessage(`后端连接失败：${error.message}`))
      .finally(() => setLoading(false));
  }, [role]);

  const studentId = dashboard?.profile.student_id;

  async function runAction(action: "ocr" | "practice" | "report") {
    if (!studentId) {
      setMessage("尚未找到学生演示数据");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      let data: ApiResult;
      if (action === "ocr") {
        data = await api<ApiResult>("/documents/demo-ocr", {
          method: "POST",
          body: JSON.stringify({
            student_id: studentId,
            document_type: role === "student" ? "comment" : "score",
            uploaded_by_role: role === "student" ? "student" : "parent",
            file_name: "demo-upload.jpg"
          })
        });
        setMessage("OCR候选结果已生成，正式数据仍需家长确认");
      } else if (action === "practice") {
        data = await api<ApiResult>("/practice-sessions/demo", {
          method: "POST",
          body: JSON.stringify({
            student_id: studentId,
            subject: "数学",
            knowledge_point: "分数应用题",
            question_count: 4
          })
        });
        setMessage("已从本地题库生成专项练习");
      } else {
        data = await api<ApiResult>("/reports/demo", {
          method: "POST",
          body: JSON.stringify({ student_id: studentId, report_type: role === "student" ? "student" : "parent" })
        });
        setMessage("AI结构化报告已生成（当前为可替换的模拟模型）");
      }
      setResult(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`app accent-${accent}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">✦</div>
          <div>
            <strong>学迹智评</strong>
            <small>AI Learning Evaluation</small>
          </div>
        </div>

        <p className="side-label">角色切换</p>
        <div className="role-list">
          {(Object.keys(roleLabels) as Role[]).map((item) => (
            <button
              className={item === role ? "role-button active" : "role-button"}
              key={item}
              onClick={() => setRole(item)}
            >
              <span>{item === "student" ? "🎓" : item === "parent" ? "👪" : "⚙️"}</span>
              <div>
                <b>{roleLabels[item]}</b>
                <small>{item === "student" ? "学习与成长" : item === "parent" ? "观察与干预" : "平台治理"}</small>
              </div>
            </button>
          ))}
        </div>

        <div className="boundary">
          <b>MVP 边界</b>
          <span>✓ 成绩/评语 OCR</span>
          <span>✓ 本地题库学习闭环</span>
          <span>— 暂无教师端</span>
          <span>— 暂无整张试卷 OCR</span>
          <span>— 不提取纸质错题</span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">XUEJI ZHICE · MVP WORKSPACE</p>
            <h1>{roleLabels[role]}</h1>
            <p>{roleDescriptions[role]}</p>
          </div>
          <div className="connection"><i />{message}</div>
        </header>

        <section className="hero panel">
          <div>
            <span className="hero-tag">三角色首版工程</span>
            <h2>
              {role === "student"
                ? `${dashboard?.profile.student_name ?? "学生"}，今天继续完成一个小目标`
                : role === "parent"
                  ? `查看 ${dashboard?.profile.student_name ?? "孩子"} 的真实学习证据`
                  : "平台服务正常，核心边界已固化"}
            </h2>
            <p>
              学年、学期、分科教材、成绩评语与本地题库数据共同构成评价基础。AI只负责结构化表达和建议，不替代确定性判题与家长确认。
            </p>
          </div>
          <div className="hero-profile">
            <span>{dashboard?.profile.grade ? `${dashboard.profile.grade}年级` : "系统"}</span>
            <b>{dashboard?.profile.term ?? "MVP v0.1"}</b>
          </div>
        </section>

        <section className="metrics">
          {(dashboard?.metrics ?? Array.from({ length: 4 }, (_, index) => ({ label: "加载中", value: "--", trend: `${index + 1}` }))).map(
            (metric) => (
              <article className="metric panel" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.trend}</small>
              </article>
            )
          )}
        </section>

        <section className="content-grid">
          <article className="panel section-card">
            <div className="section-title">
              <div>
                <span>CORE WORKFLOW</span>
                <h3>{role === "admin" ? "平台待办" : "当前任务"}</h3>
              </div>
              <button onClick={() => void runAction("practice")} disabled={loading || role === "admin"}>
                生成题库练习
              </button>
            </div>
            <div className="task-list">
              {dashboard?.tasks.map((task) => (
                <div className="task-row" key={task.title}>
                  <div className="task-icon">{task.type === "重点" ? "!" : "✓"}</div>
                  <div>
                    <b>{task.title}</b>
                    <span>{task.type} · 预计 {task.minutes} 分钟</span>
                  </div>
                  <em>{task.minutes}m</em>
                </div>
              ))}
            </div>
          </article>

          <article className="panel section-card">
            <div className="section-title">
              <div>
                <span>QUICK ACTIONS</span>
                <h3>功能验证</h3>
              </div>
            </div>
            <div className="actions">
              <button onClick={() => void runAction("ocr")} disabled={loading || role === "admin"}>
                <span>📷</span>
                <b>模拟成绩/评语 OCR</b>
                <small>生成候选字段与置信度</small>
              </button>
              <button onClick={() => void runAction("practice")} disabled={loading || role === "admin"}>
                <span>🧩</span>
                <b>生成本地题库练习</b>
                <small>不依赖纸质试卷识别</small>
              </button>
              <button onClick={() => void runAction("report")} disabled={loading || role === "admin"}>
                <span>🤖</span>
                <b>生成角色版 AI 报告</b>
                <small>学生版或家长版结构化输出</small>
              </button>
            </div>
          </article>
        </section>

        <section className="content-grid lower">
          <article className="panel section-card">
            <div className="section-title">
              <div>
                <span>EXPLAINABILITY</span>
                <h3>系统通知与判断依据</h3>
              </div>
            </div>
            {(dashboard?.notices ?? []).map((notice) => (
              <div className="notice" key={notice.title}>
                <b>{notice.title}</b>
                <p>{notice.content}</p>
              </div>
            ))}
            <div className="evidence-row">
              <span><i className="fact" />直接事实</span>
              <span><i className="high" />较高可信判断</span>
              <span><i className="possible" />可能情况</span>
              <span><i className="lack" />数据不足</span>
            </div>
          </article>

          <article className="panel result-card">
            <div className="section-title">
              <div>
                <span>API RESULT</span>
                <h3>最近一次接口结果</h3>
              </div>
            </div>
            <pre>{result ? JSON.stringify(result, null, 2) : "点击上方功能按钮，查看后端真实返回。"}</pre>
          </article>
        </section>
      </main>
    </div>
  );
}
