import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, AuthData, getStoredAuth, storeAuth } from "./api";

type View = "overview" | "students" | "practice" | "documents" | "questions";
type Student = { id: string; nickname: string; current_grade: number; current_term: string; daily_minutes_limit: number };
type Dashboard = {
  role: string;
  identity: { display_name: string; email: string; role: string; family_id: string | null };
  metrics: { label: string; value: string | number }[];
  actions: { title: string; route: string; enabled: boolean }[];
  notices: { level: string; text: string }[];
};
type Question = {
  id: string; question_code: string; subject: string; grade: number; display_type: string; difficulty: number;
  stem: { blocks: { type: string; value?: string }[] };
  options: { key: string; content: { blocks: { type: string; value?: string }[] } }[];
};
type PracticeSession = { id: string; status: string; subject: string; total_count: number; correct_count: number };
type PracticeItem = { id: string; sequence_no: number; question: Question };

const roleNames: Record<string, string> = { parent: "家长", student: "学生", admin: "平台管理员" };

function textFromBlocks(content?: { blocks?: { value?: string }[] }): string {
  return content?.blocks?.map((block) => block.value ?? "").join(" ") ?? "";
}

function LoginPage({ onAuthenticated }: { onAuthenticated: (value: AuthData) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("parent@example.com");
  const [password, setPassword] = useState("Parent123!");
  const [displayName, setDisplayName] = useState("新家长");
  const [familyName, setFamilyName] = useState("我的家庭");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const response = await api<AuthData>(mode === "login" ? "/auth/login" : "/auth/register/parent", {
        method: "POST",
        body: JSON.stringify(mode === "login" ? { email, password } : { email, password, display_name: displayName, family_name: familyName })
      }, null);
      storeAuth(response.data); onAuthenticated(response.data);
    } catch (error) { setMessage(error instanceof Error ? error.message : "登录失败"); }
    finally { setBusy(false); }
  }

  return <main className="auth-shell">
    <section className="auth-brand"><div className="logo-mark">学</div><p className="eyebrow">XUEJI ZHICE · v0.2</p><h1>把学习证据变成可执行的下一步</h1><p>真实登录身份、家庭数据隔离、本地题库练习、可追溯判题与错题复习。</p><div className="security-points"><span>身份由后端令牌确认</span><span>跨家庭访问默认拒绝</span><span>演示功能生产环境关闭</span></div></section>
    <form className="auth-card" onSubmit={submit}><div className="tabs"><button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>登录</button><button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>家长注册</button></div>
      <label>邮箱<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required /></label>
      <label>密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" minLength={8} required /></label>
      {mode === "register" && <><label>显示名称<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label><label>家庭名称<input value={familyName} onChange={(event) => setFamilyName(event.target.value)} required /></label></>}
      {message && <div className="form-error" role="alert">{message}</div>}
      <button className="primary" disabled={busy}>{busy ? "处理中…" : mode === "login" ? "安全登录" : "创建家庭账号"}</button>
      <details><summary>本地演示账号</summary><p>家长：parent@example.com / Parent123!</p><p>学生：student@example.com / Student123!</p><p>管理员：admin@example.com / Admin123!</p></details>
    </form>
  </main>;
}

export default function App() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [view, setView] = useState<View>("overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedStudent, setSelectedStudent] = useState("");
  const [message, setMessage] = useState("正在读取工作台…");
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [practiceItem, setPracticeItem] = useState<PracticeItem | null>(null);
  const [choice, setChoice] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [lastFeedback, setLastFeedback] = useState("");

  const loadWorkspace = useCallback(async () => {
    if (!auth) return; setBusy(true);
    try {
      const board = await api<Dashboard>("/dashboard", {}, auth); setDashboard(board.data);
      if (auth.user.role === "admin") {
        setStudents([]); setSelectedStudent("");
        const response = await api<Question[]>("/questions?page=1&page_size=50", {}, auth); setQuestions(response.data);
      } else {
        const response = await api<Student[]>("/students?page=1&page_size=50", {}, auth); setStudents(response.data);
        setSelectedStudent((current) => current || response.data[0]?.id || "");
      }
      setMessage("数据已安全加载");
    } catch (error) { setMessage(error instanceof Error ? error.message : "加载失败"); }
    finally { setBusy(false); }
  }, [auth]);
  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);

  const navigation = useMemo(() => {
    const common: { id: View; label: string }[] = [{ id: "overview", label: "首页" }];
    if (auth?.user.role === "admin") { common.push({ id: "questions", label: "题库管理" }); return common; }
    if (auth?.user.role !== "student") common.push({ id: "students", label: "学生档案" });
    common.push({ id: "practice", label: "练习与错题" }, { id: "documents", label: "资料上传" }); return common;
  }, [auth?.user.role]);

  async function logout() {
    if (auth) try { await api("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: auth.refresh_token }) }, auth); } catch { /* local logout */ }
    storeAuth(null); setAuth(null);
  }
  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!auth) return; const form = new FormData(event.currentTarget); setBusy(true);
    try { await api("/students", { method: "POST", body: JSON.stringify({ nickname: form.get("nickname"), current_grade: Number(form.get("grade")) }) }, auth); event.currentTarget.reset(); await loadWorkspace(); setMessage("学生档案已创建并写入审计记录"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "创建失败"); } finally { setBusy(false); }
  }
  async function loadNext(sessionId: string) { if (!auth) return; const response = await api<PracticeItem | null>(`/practice-sessions/${sessionId}/next`, {}, auth); setPracticeItem(response.data); setChoice(""); setTextAnswer(""); }
  async function createPractice() {
    if (!auth || !selectedStudent) return; setBusy(true); setLastFeedback("");
    try { const response = await api<PracticeSession>("/practice-sessions", { method: "POST", body: JSON.stringify({ student_id: selectedStudent, subject: "数学", question_count: 3, practice_type: "targeted" }) }, auth); setSession(response.data); await loadNext(response.data.id); setMessage("练习已生成，每道题都保存了不可变快照"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "生成失败"); } finally { setBusy(false); }
  }
  async function submitAnswer() {
    if (!auth || !session || !practiceItem) return; const isChoice = practiceItem.question.display_type.includes("choice"); const answer = isChoice ? { selected: [choice] } : { value: textAnswer }; setBusy(true);
    try { const response = await api<{ is_correct: boolean; feedback: string }>(`/practice-sessions/${session.id}/answers`, { method: "POST", body: JSON.stringify({ practice_item_id: practiceItem.id, answer }) }, auth); setLastFeedback(response.data.feedback); await loadNext(session.id); await loadWorkspace(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "提交失败"); } finally { setBusy(false); }
  }
  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!auth || !selectedStudent) return; const data = new FormData(event.currentTarget); data.set("student_id", selectedStudent); setBusy(true);
    try { const response = await api<{ id: string; status: string }>("/documents/upload", { method: "POST", body: data }, auth); setMessage(`资料已进入私有存储，状态：${response.data.status}`); event.currentTarget.reset(); await loadWorkspace(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "上传失败"); } finally { setBusy(false); }
  }

  if (!auth) return <LoginPage onAuthenticated={setAuth} />;
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="logo-mark">学</div><div><strong>学迹智评</strong><small>v0.2 安全基线版</small></div></div><div className="identity-card"><b>{auth.user.display_name}</b><span>{roleNames[auth.user.role]}</span><small>{auth.user.email}</small></div><nav aria-label="主导航">{navigation.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.label}</button>)}</nav><button className="logout" onClick={() => void logout()}>退出登录</button></aside>
    <main className="workspace"><header className="topbar"><div><p className="eyebrow">SECURE LEARNING WORKSPACE</p><h1>{navigation.find((item) => item.id === view)?.label}</h1></div><div className="status"><i />{busy ? "正在处理…" : message}</div></header>
      {view === "overview" && <><section className="hero-card"><div><span>真实身份 · 家庭隔离 · 可审计</span><h2>{dashboard?.identity.display_name ?? auth.user.display_name}，欢迎回来</h2><p>系统依据登录令牌确认身份。学习结论按“事实、判断、数据不足”分层展示。</p></div><div className="hero-role">{roleNames[auth.user.role]}</div></section><section className="metric-grid">{dashboard?.metrics.map((metric) => <article className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></article>)}</section><section className="two-column"><article className="panel"><h3>下一步操作</h3>{dashboard?.actions.map((action) => <button className="action-row" disabled={!action.enabled} key={action.title} onClick={() => setView(action.route.includes("practice") ? "practice" : action.route.includes("documents") ? "documents" : "questions")}>{action.title}<span>→</span></button>)}</article><article className="panel"><h3>判断依据</h3>{dashboard?.notices.map((notice) => <div className={`notice ${notice.level}`} key={notice.text}>{notice.text}</div>)}</article></section></>}
      {view === "students" && <section className="two-column"><article className="panel"><h3>家庭学生档案</h3><div className="student-list">{students.map((student) => <button key={student.id} className={selectedStudent === student.id ? "student-card selected" : "student-card"} onClick={() => setSelectedStudent(student.id)}><b>{student.nickname}</b><span>{student.current_grade}年级 · {student.current_term}</span><small>每日上限 {student.daily_minutes_limit} 分钟</small></button>)}</div></article>{auth.user.role !== "student" && <form className="panel form-panel" onSubmit={createStudent}><h3>新建学生档案</h3><label>昵称<input name="nickname" required maxLength={80} /></label><label>当前年级<input name="grade" type="number" min="1" max="12" defaultValue="8" required /></label><button className="primary" disabled={busy}>创建并记录审计</button></form>}</section>}
      {view === "practice" && <section className="practice-layout"><article className="panel practice-control"><h3>数学短练习</h3><label>选择学生<select value={selectedStudent} onChange={(event) => setSelectedStudent(event.target.value)}>{students.map((student) => <option key={student.id} value={student.id}>{student.nickname}</option>)}</select></label><button className="primary" onClick={() => void createPractice()} disabled={busy || !selectedStudent}>生成3题练习</button>{session && <div className="session-summary"><b>会话 {session.id.slice(0, 8)}</b><span>{session.subject} · 共{session.total_count}题</span></div>}</article><article className="panel question-panel">{practiceItem ? <><span className="question-index">第 {practiceItem.sequence_no} 题 · {practiceItem.question.question_code}</span><h3>{textFromBlocks(practiceItem.question.stem)}</h3>{practiceItem.question.options.length > 0 ? <div className="options">{practiceItem.question.options.map((option) => <label key={option.key} className={choice === option.key ? "selected" : ""}><input type="radio" name="answer" value={option.key} checked={choice === option.key} onChange={() => setChoice(option.key)} /><b>{option.key}</b>{textFromBlocks(option.content)}</label>)}</div> : <label className="math-answer">填写答案<input value={textAnswer} onChange={(event) => setTextAnswer(event.target.value)} placeholder="支持 √3、sqrt(3)、全角数字等" /></label>}<button className="primary" disabled={busy || (!choice && !textAnswer)} onClick={() => void submitAnswer()}>提交答案</button></> : <div className="empty-state"><b>{session ? "本次练习已完成" : "尚未开始练习"}</b><p>{lastFeedback || "选择学生后生成3道短练习。"}</p></div>}{lastFeedback && practiceItem && <div className="feedback">{lastFeedback}</div>}</article></section>}
      {view === "documents" && <section className="two-column"><form className="panel form-panel" onSubmit={uploadDocument}><h3>上传成绩或评语</h3><label>学生<select value={selectedStudent} onChange={(event) => setSelectedStudent(event.target.value)}>{students.map((student) => <option key={student.id} value={student.id}>{student.nickname}</option>)}</select></label><label>资料类型<select name="document_type" defaultValue="score"><option value="score">成绩</option><option value="comment">教师评语</option><option value="evaluation">学校评价</option><option value="textbook_cover">教材封面</option></select></label><label>文件<input name="file" type="file" accept="image/png,image/jpeg,image/webp,application/pdf" required /></label><button className="primary" disabled={busy || !selectedStudent}>上传到私有存储</button></form><article className="panel"><h3>安全处理流程</h3><ol className="steps"><li>校验文件类型和大小</li><li>计算 SHA-256 并检测重复</li><li>保存到家庭隔离目录</li><li>家长确认后进入正式档案</li></ol><div className="notice insufficient_data">当前版本保留人工确认兜底；真实 OCR 适配器在下一阶段启用。</div></article></section>}
      {view === "questions" && <section className="panel"><div className="section-heading"><div><h3>已审核发布题库</h3><p>题目身份与内容版本已分离，历史作答使用版本快照。</p></div><span>{questions.length} 题</span></div><div className="question-table">{questions.map((question) => <article key={question.id}><div><b>{question.question_code}</b><span>{question.subject} · {question.grade}年级 · 难度{question.difficulty}</span></div><p>{textFromBlocks(question.stem)}</p><em>{question.display_type}</em></article>)}</div></section>}
    </main></div>;
}
