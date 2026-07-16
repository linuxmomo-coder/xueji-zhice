import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { api, AuthData, getStoredAuth, storeAuth } from "./api";

type Role = "parent" | "student" | "admin";
type View = "overview" | "students" | "practice" | "documents" | "questions";
type Student = {
  id: string;
  user_id: string | null;
  nickname: string;
  current_grade: number;
  current_term: string;
  daily_minutes_limit: number;
};
type Dashboard = {
  role: Role;
  identity: { display_name: string; email: string; role: Role; family_id: string | null };
  metrics: { label: string; value: string | number }[];
  actions: { title: string; route: string; enabled: boolean; reason?: string | null }[];
  notices: { level: string; text: string }[];
  generated_at: string;
};
type ContentBlock = {
  type: string;
  value?: string;
  asset_url?: string;
  alt_text?: string;
};
type Question = {
  id: string;
  question_code: string;
  subject: string;
  grade: number;
  display_type: string;
  difficulty: number;
  stem: { blocks: ContentBlock[] };
  options: { key: string; content: { blocks: ContentBlock[] } }[];
};
type SubjectAvailability = { subject: string; question_count: number };
type PracticeSession = {
  id: string;
  status: string;
  subject: string;
  total_count: number;
  correct_count: number;
};
type PracticeItem = { id: string; sequence_no: number; question: Question };
type WrongQuestion = {
  id: string;
  question_id: string;
  wrong_count: number;
  state: string;
  last_wrong_at: string;
  next_review_at: string | null;
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
type NavigationItem = { id: View; label: string };

const roleNames: Record<Role, string> = {
  parent: "家长",
  student: "学生",
  admin: "平台管理员"
};

const roleOptions: { value: Role; title: string; description: string; icon: string }[] = [
  { value: "parent", title: "家长登录", description: "管理学生档案、资料确认和学习安排", icon: "家" },
  { value: "student", title: "学生登录", description: "完成练习、复习错题和上传学习资料", icon: "学" },
  { value: "admin", title: "管理员登录", description: "管理题库、数据质量和平台配置", icon: "管" }
];

const navigationByRole: Record<Role, NavigationItem[]> = {
  parent: [
    { id: "overview", label: "家庭首页" },
    { id: "students", label: "学生档案" },
    { id: "practice", label: "练习与错题" },
    { id: "documents", label: "资料上传与确认" }
  ],
  student: [
    { id: "overview", label: "学习首页" },
    { id: "practice", label: "练习与错题" },
    { id: "documents", label: "资料上传" }
  ],
  admin: [
    { id: "overview", label: "平台概览" },
    { id: "questions", label: "题库管理" }
  ]
};

const overviewCopy: Record<Role, { tag: string; description: string }> = {
  parent: {
    tag: "家庭数据 · 监护权限 · 学习证据",
    description: "这里仅展示当前家庭在数据库中的学生、练习、错题和待确认资料。"
  },
  student: {
    tag: "本人档案 · 实际练习 · 错题复习",
    description: "这里仅展示当前学生账号有权访问的学习记录和可用题库。"
  },
  admin: {
    tag: "平台数据 · 题库状态 · 运行结果",
    description: "这里展示当前运行环境数据库中的题库、学生、练习和资料状态。"
  }
};

function textFromBlocks(content?: { blocks?: ContentBlock[] }): string {
  return content?.blocks?.map((block) => block.value ?? "").join(" ").trim() ?? "";
}

function renderBlocks(content?: { blocks?: ContentBlock[] }): ReactNode[] {
  return (content?.blocks ?? []).map((block, index) => {
    if (block.type === "asset" && block.asset_url) {
      return <img key={`${block.asset_url}-${index}`} src={block.asset_url} alt={block.alt_text ?? "题目图片"} className="question-asset" />;
    }
    return <span key={`${block.type}-${index}`}>{block.value ?? ""}</span>;
  });
}

function viewFromRoute(route: string): View {
  if (route.includes("students")) return "students";
  if (route.includes("practice")) return "practice";
  if (route.includes("documents")) return "documents";
  if (route.includes("questions")) return "questions";
  return "overview";
}

function LoginPage({ onAuthenticated }: { onAuthenticated: (value: AuthData) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState<Role>("parent");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  function changeMode(nextMode: "login" | "register") {
    setMode(nextMode);
    setMessage("");
    if (nextMode === "register") setRole("parent");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await api<AuthData>(
        mode === "login" ? "/auth/login" : "/auth/register/parent",
        {
          method: "POST",
          body: JSON.stringify(
            mode === "login"
              ? { email, password, role }
              : { email, password, display_name: displayName, family_name: familyName }
          )
        },
        null
      );
      storeAuth(response.data);
      onAuthenticated(response.data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-brand">
        <div className="logo-mark">学</div>
        <p className="eyebrow">XUEJI ZHICE · v0.2.2</p>
        <h1>按真实身份进入各自的学习空间</h1>
        <p>登录时选择身份，后端会校验账号角色；登录后只显示该角色有权使用的功能和实际业务数据。</p>
        <div className="security-points">
          <span>角色与账号必须匹配</span>
          <span>家庭和学生数据隔离</span>
          <span>界面不使用固化统计数据</span>
        </div>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <div className="tabs">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => changeMode("login")}>登录</button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => changeMode("register")}>家长注册</button>
        </div>
        {mode === "login" ? (
          <fieldset className="role-selector">
            <legend>选择登录身份</legend>
            <div className="role-grid">
              {roleOptions.map((item) => (
                <button type="button" key={item.value} className={role === item.value ? "role-option selected" : "role-option"} aria-pressed={role === item.value} onClick={() => setRole(item.value)}>
                  <span>{item.icon}</span><div><b>{item.title}</b><small>{item.description}</small></div>
                </button>
              ))}
            </div>
          </fieldset>
        ) : <div className="registration-note">当前开放家长注册。学生账号由家长创建并绑定，管理员账号由平台授权开通。</div>}
        <label>邮箱<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" placeholder="请输入账号邮箱" required /></label>
        <label>密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} placeholder="请输入密码" required /></label>
        {mode === "register" && <>
          <label>显示名称<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="家长姓名或称呼" required /></label>
          <label>家庭名称<input value={familyName} onChange={(event) => setFamilyName(event.target.value)} placeholder="例如：小明家庭" required /></label>
        </>}
        {message && <div className="form-error" role="alert">{message}</div>}
        <button className="primary" disabled={busy}>{busy ? "处理中…" : mode === "login" ? `以${roleNames[role]}身份登录` : "创建家长账号"}</button>
      </form>
    </main>
  );
}

export default function App() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [view, setView] = useState<View>("overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionTotal, setQuestionTotal] = useState(0);
  const [availableSubjects, setAvailableSubjects] = useState<SubjectAvailability[]>([]);
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestion[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentDrafts, setDocumentDrafts] = useState<Record<string, string>>({});
  const [selectedStudent, setSelectedStudent] = useState("");
  const [practiceSubject, setPracticeSubject] = useState("");
  const [questionCount, setQuestionCount] = useState(1);
  const [message, setMessage] = useState("正在读取服务器数据…");
  const [busy, setBusy] = useState(false);
  const [subjectsBusy, setSubjectsBusy] = useState(false);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [practiceItem, setPracticeItem] = useState<PracticeItem | null>(null);
  const [choice, setChoice] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [lastFeedback, setLastFeedback] = useState("");

  const role = auth?.user.role ?? "parent";
  const navigation = useMemo(() => navigationByRole[role], [role]);
  const selectedStudentRecord = useMemo(() => students.find((student) => student.id === selectedStudent) ?? null, [students, selectedStudent]);
  const selectedSubjectAvailability = useMemo(() => availableSubjects.find((item) => item.subject === practiceSubject) ?? null, [availableSubjects, practiceSubject]);
  const maxQuestionCount = Math.min(10, selectedSubjectAvailability?.question_count ?? 0);

  const loadWorkspace = useCallback(async () => {
    if (!auth) return;
    setBusy(true);
    try {
      const board = await api<Dashboard>("/dashboard", {}, auth);
      setDashboard(board.data);
      if (auth.user.role === "admin") {
        setStudents([]);
        setSelectedStudent("");
        setAvailableSubjects([]);
        const questionResponse = await api<Question[]>("/questions?page=1&page_size=100", {}, auth);
        setQuestions(questionResponse.data);
        setQuestionTotal(Number(questionResponse.meta.total ?? questionResponse.data.length));
      } else {
        setQuestions([]);
        setQuestionTotal(0);
        const studentResponse = await api<Student[]>("/students?page=1&page_size=100", {}, auth);
        setStudents(studentResponse.data);
        setSelectedStudent((current) => studentResponse.data.some((student) => student.id === current) ? current : studentResponse.data[0]?.id ?? "");
      }
      setMessage("已加载服务器业务数据");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载失败");
    } finally {
      setBusy(false);
    }
  }, [auth]);

  const loadStudentRelated = useCallback(async () => {
    if (!auth || !selectedStudent || auth.user.role === "admin") {
      setWrongQuestions([]);
      setDocuments([]);
      return;
    }
    try {
      const [wrongResponse, documentResponse] = await Promise.all([
        api<WrongQuestion[]>(`/students/${selectedStudent}/wrong-questions`, {}, auth),
        api<DocumentRecord[]>(`/documents?student_id=${selectedStudent}&page_size=100`, {}, auth)
      ]);
      setWrongQuestions(wrongResponse.data);
      setDocuments(documentResponse.data);
      const drafts: Record<string, string> = {};
      for (const item of documentResponse.data) {
        drafts[item.id] = JSON.stringify(item.confirmed_data ?? item.structured_data ?? {}, null, 2);
      }
      setDocumentDrafts(drafts);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "学生关联数据加载失败");
    }
  }, [auth, selectedStudent]);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);
  useEffect(() => { void loadStudentRelated(); }, [loadStudentRelated]);

  useEffect(() => {
    if (!auth || auth.user.role === "admin" || !selectedStudentRecord) {
      setAvailableSubjects([]);
      setPracticeSubject("");
      return;
    }
    let cancelled = false;
    setSubjectsBusy(true);
    api<SubjectAvailability[]>(`/questions/subjects?grade=${selectedStudentRecord.current_grade}`, {}, auth)
      .then((response) => {
        if (cancelled) return;
        setAvailableSubjects(response.data);
        setPracticeSubject((current) => response.data.some((item) => item.subject === current) ? current : response.data[0]?.subject ?? "");
      })
      .catch((error) => {
        if (!cancelled) {
          setAvailableSubjects([]);
          setPracticeSubject("");
          setMessage(error instanceof Error ? error.message : "题库科目加载失败");
        }
      })
      .finally(() => { if (!cancelled) setSubjectsBusy(false); });
    return () => { cancelled = true; };
  }, [auth, selectedStudentRecord]);

  useEffect(() => {
    const maximum = Math.min(10, selectedSubjectAvailability?.question_count ?? 0);
    setQuestionCount((current) => maximum > 0 ? Math.min(Math.max(current, 1), maximum) : 1);
    setSession(null);
    setPracticeItem(null);
    setLastFeedback("");
  }, [selectedStudent, practiceSubject, selectedSubjectAvailability?.question_count]);

  async function logout() {
    const latestAuth = getStoredAuth() ?? auth;
    if (latestAuth) {
      try {
        await api("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: latestAuth.refresh_token }) }, latestAuth);
      } catch {
        // Local logout still proceeds if the network is unavailable.
      }
    }
    storeAuth(null);
    setAuth(null);
    setDashboard(null);
    setView("overview");
  }

  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth || auth.user.role !== "parent") return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api("/students", { method: "POST", body: JSON.stringify({ nickname: form.get("nickname"), current_grade: Number(form.get("grade")), current_term: form.get("term"), daily_minutes_limit: Number(form.get("daily_minutes_limit")) }) }, auth);
      event.currentTarget.reset();
      await loadWorkspace();
      setMessage("学生档案已创建");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function createStudentAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth || !selectedStudentRecord || selectedStudentRecord.user_id) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api(`/students/${selectedStudentRecord.id}/account`, { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password"), display_name: form.get("display_name") || selectedStudentRecord.nickname }) }, auth);
      event.currentTarget.reset();
      await loadWorkspace();
      setMessage("学生登录账号已创建并绑定");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "学生账号创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function createPractice() {
    if (!auth || !selectedStudent || !practiceSubject || questionCount < 1) return;
    setBusy(true);
    setLastFeedback("");
    try {
      const response = await api<PracticeSession>("/practice-sessions", { method: "POST", body: JSON.stringify({ student_id: selectedStudent, subject: practiceSubject, question_count: questionCount, practice_type: "targeted" }) }, auth);
      setSession(response.data);
      await loadNext(response.data.id);
      setMessage(`已从该学生年级的已发布题库生成 ${response.data.total_count} 道${response.data.subject}题`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function loadNext(sessionId: string) {
    if (!auth) return;
    const response = await api<PracticeItem | null>(`/practice-sessions/${sessionId}/next`, {}, auth);
    setPracticeItem(response.data);
    setChoice("");
    setTextAnswer("");
  }

  async function submitAnswer() {
    if (!auth || !session || !practiceItem) return;
    const isChoice = practiceItem.question.display_type.includes("choice");
    const answer = isChoice ? { selected: [choice] } : { value: textAnswer };
    setBusy(true);
    try {
      const response = await api<{ is_correct: boolean; feedback: string }>(`/practice-sessions/${session.id}/answers`, { method: "POST", body: JSON.stringify({ practice_item_id: practiceItem.id, answer }) }, auth);
      setLastFeedback(response.data.feedback);
      await loadNext(session.id);
      await Promise.all([loadWorkspace(), loadStudentRelated()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth || !selectedStudent) return;
    const data = new FormData(event.currentTarget);
    data.set("student_id", selectedStudent);
    setBusy(true);
    try {
      const response = await api<{ id: string; status: string }>("/documents/upload", { method: "POST", body: data }, auth);
      setMessage(`资料已保存，当前状态：${response.data.status}`);
      event.currentTarget.reset();
      await Promise.all([loadWorkspace(), loadStudentRelated()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDocument(documentId: string) {
    if (!auth || auth.user.role !== "parent") return;
    try {
      const confirmedData = JSON.parse(documentDrafts[documentId] || "{}") as Record<string, unknown>;
      setBusy(true);
      await api(`/documents/${documentId}/confirm`, { method: "POST", body: JSON.stringify({ confirmed_data: confirmedData }) }, auth);
      await Promise.all([loadWorkspace(), loadStudentRelated()]);
      setMessage("资料已确认并进入正式档案");
    } catch (error) {
      setMessage(error instanceof SyntaxError ? "确认内容必须是合法JSON" : error instanceof Error ? error.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  if (!auth) return <LoginPage onAuthenticated={setAuth} />;

  const updateTime = dashboard?.generated_at ? new Date(dashboard.generated_at).toLocaleString("zh-CN", { hour12: false }) : null;
  const copy = overviewCopy[auth.user.role];

  return (
    <div className={`app-shell role-${auth.user.role}`}>
      <aside className="sidebar">
        <div className="brand"><div className="logo-mark">学</div><div><strong>学迹智评</strong><small>v0.2.2 业务数据版</small></div></div>
        <div className="identity-card"><b>{auth.user.display_name}</b><span>{roleNames[auth.user.role]}</span><small>{auth.user.email}</small></div>
        <nav aria-label={`${roleNames[auth.user.role]}功能导航`}>
          {navigation.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.label}</button>)}
        </nav>
        <button className="logout" onClick={() => void logout()}>退出登录</button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div><p className="eyebrow">{roleNames[auth.user.role].toUpperCase()} WORKSPACE</p><h1>{navigation.find((item) => item.id === view)?.label}</h1></div>
          <div className="status"><i />{busy ? "正在处理…" : updateTime ? `${message} · 接口生成于 ${updateTime}` : message}</div>
        </header>

        {view === "overview" && <>
          <section className="hero-card"><div><span>{copy.tag}</span><h2>{dashboard?.identity.display_name ?? auth.user.display_name}，欢迎回来</h2><p>{copy.description}</p></div><div className="hero-role">{roleNames[auth.user.role]}</div></section>
          {dashboard ? <section className="metric-grid">{dashboard.metrics.map((metric) => <article className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></article>)}</section> : <section className="panel loading-panel">正在读取业务统计…</section>}
          <section className="two-column">
            <article className="panel"><h3>可用功能</h3>{dashboard?.actions.map((action) => <button className="action-row" disabled={!action.enabled} key={action.title} onClick={() => setView(viewFromRoute(action.route))} title={!action.enabled ? action.reason ?? "当前不可用" : undefined}><div><b>{action.title}</b>{!action.enabled && action.reason && <small>{action.reason}</small>}</div><span>→</span></button>)}</article>
            <article className="panel"><h3>实时状态</h3>{dashboard?.notices.length ? dashboard.notices.map((notice) => <div className={`notice ${notice.level}`} key={notice.text}>{notice.text}</div>) : <div className="empty-inline">当前没有需要提示的业务状态。</div>}</article>
          </section>
        </>}

        {view === "students" && auth.user.role === "parent" && <section className="two-column">
          <article className="panel"><h3>家庭学生档案</h3>{students.length ? <div className="student-list">{students.map((student) => <button key={student.id} className={selectedStudent === student.id ? "student-card selected" : "student-card"} onClick={() => setSelectedStudent(student.id)}><b>{student.nickname}</b><span>{student.current_grade}年级 · {student.current_term}</span><small>{student.user_id ? "已绑定学生登录账号" : "尚未绑定登录账号"} · 每日上限 {student.daily_minutes_limit} 分钟</small></button>)}</div> : <div className="empty-state compact"><b>暂无学生档案</b><p>创建后，系统会重新读取数据库。</p></div>}</article>
          <div>
            <form className="panel form-panel" onSubmit={createStudent}><h3>新建学生档案</h3><label>昵称<input name="nickname" required maxLength={80} placeholder="学生昵称" /></label><label>当前年级<input name="grade" type="number" min="1" max="12" placeholder="1-12" required /></label><label>当前学期<input name="term" maxLength={60} placeholder="例如：2026-2027 第一学期" required /></label><label>每日学习上限（分钟）<input name="daily_minutes_limit" type="number" min="5" max="240" defaultValue="50" required /></label><button className="primary" disabled={busy}>创建学生档案</button></form>
            {selectedStudentRecord && !selectedStudentRecord.user_id && <form className="panel form-panel" onSubmit={createStudentAccount}><h3>为{selectedStudentRecord.nickname}创建登录账号</h3><label>登录邮箱<input name="email" type="email" required placeholder="student@example.com" /></label><label>显示名称<input name="display_name" defaultValue={selectedStudentRecord.nickname} /></label><label>初始密码<input name="password" type="password" minLength={8} required autoComplete="new-password" /></label><button className="primary" disabled={busy}>创建并绑定学生账号</button></form>}
          </div>
        </section>}

        {view === "practice" && <>
          <section className="practice-layout">
            <article className="panel practice-control"><h3>按学生年级和实际题库生成练习</h3>{students.length ? <><label>学生<select value={selectedStudent} onChange={(event) => setSelectedStudent(event.target.value)} disabled={auth.user.role === "student" && students.length === 1}>{students.map((student) => <option key={student.id} value={student.id}>{student.nickname} · {student.current_grade}年级</option>)}</select></label><label>科目<select value={practiceSubject} onChange={(event) => setPracticeSubject(event.target.value)} disabled={subjectsBusy || availableSubjects.length === 0}>{availableSubjects.map((item) => <option key={item.subject} value={item.subject}>{item.subject}（{item.question_count}题可用）</option>)}</select></label><label>题目数量<select value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))} disabled={maxQuestionCount === 0}>{Array.from({ length: maxQuestionCount }, (_, index) => index + 1).map((count) => <option key={count} value={count}>{count}题</option>)}</select></label>{availableSubjects.length === 0 && !subjectsBusy && <div className="notice insufficient_data">该学生当前年级没有已审核发布的题目。</div>}<button className="primary" onClick={() => void createPractice()} disabled={busy || subjectsBusy || !selectedStudent || !practiceSubject || maxQuestionCount === 0}>{practiceSubject ? `生成${questionCount}题${practiceSubject}练习` : "暂无可用题目"}</button></> : <div className="empty-state compact"><b>没有可用学生档案</b><p>{auth.user.role === "parent" ? "请先在学生档案中创建学生。" : "请联系家长完成账号绑定。"}</p></div>}{session && <div className="session-summary"><b>会话 {session.id.slice(0, 8)}</b><span>{session.subject} · 共{session.total_count}题</span></div>}</article>
            <article className="panel question-panel">{practiceItem ? <><span className="question-index">第 {practiceItem.sequence_no} 题 · {practiceItem.question.question_code}</span><h3>{renderBlocks(practiceItem.question.stem)}</h3>{practiceItem.question.options.length > 0 ? <div className="options">{practiceItem.question.options.map((option) => <label key={option.key} className={choice === option.key ? "selected" : ""}><input type="radio" name="answer" value={option.key} checked={choice === option.key} onChange={() => setChoice(option.key)} /><b>{option.key}</b>{renderBlocks(option.content)}</label>)}</div> : <label className="math-answer">填写答案<input value={textAnswer} onChange={(event) => setTextAnswer(event.target.value)} placeholder="支持 √3、sqrt(3)、全角数字等" /></label>}<button className="primary" disabled={busy || (!choice && !textAnswer)} onClick={() => void submitAnswer()}>提交答案</button></> : <div className="empty-state"><b>{session ? "本次练习已完成" : "尚未开始练习"}</b><p>{lastFeedback || "选择学生、科目和题量后生成练习。"}</p></div>}{lastFeedback && practiceItem && <div className="feedback">{lastFeedback}</div>}</article>
          </section>
          <section className="panel"><div className="section-heading"><div><h3>错题复习记录</h3><p>以下数据来自当前学生真实错题记录。</p></div><span>{wrongQuestions.length} 题</span></div>{wrongQuestions.length ? <div className="question-table">{wrongQuestions.map((wrong) => <article key={wrong.id}><div><b>题目 {wrong.question_id.slice(0, 8)}</b><span>累计错误 {wrong.wrong_count} 次</span></div><p>状态：{wrong.state} · 最近错误：{new Date(wrong.last_wrong_at).toLocaleString("zh-CN")}</p><em>{wrong.next_review_at ? `建议复习：${new Date(wrong.next_review_at).toLocaleDateString("zh-CN")}` : "待安排"}</em></article>)}</div> : <div className="empty-state"><b>当前没有错题记录</b><p>错题会在真实作答判分后自动进入这里。</p></div>}</section>
        </>}

        {view === "documents" && <section className="two-column">
          <div>{students.length ? <form className="panel form-panel" onSubmit={uploadDocument}><h3>上传成绩或评语</h3><label>学生<select value={selectedStudent} onChange={(event) => setSelectedStudent(event.target.value)} disabled={auth.user.role === "student" && students.length === 1}>{students.map((student) => <option key={student.id} value={student.id}>{student.nickname}</option>)}</select></label><label>资料类型<select name="document_type" defaultValue="score"><option value="score">成绩</option><option value="comment">教师评语</option><option value="evaluation">学校评价</option><option value="textbook_cover">教材封面</option></select></label><label>文件<input name="file" type="file" accept="image/png,image/jpeg,image/webp,application/pdf" required /></label><button className="primary" disabled={busy || !selectedStudent}>上传到私有存储</button></form> : <article className="panel empty-state"><b>没有可上传资料的学生档案</b><p>{auth.user.role === "parent" ? "请先创建学生档案。" : "请联系家长绑定学生档案。"}</p></article>}<article className="panel"><h3>当前真实处理能力</h3><ol className="steps"><li>校验文件类型和大小</li><li>计算 SHA-256 并检测重复</li><li>保存到家庭隔离目录</li><li>家长核对结构化内容后确认</li></ol><div className="notice insufficient_data">当前版本尚未启用真实OCR；系统会明确显示人工确认状态，不会把未识别资料冒充正式学习证据。</div></article></div>
          <article className="panel"><div className="section-heading"><div><h3>资料记录</h3><p>按当前学生从数据库读取。</p></div><span>{documents.length} 份</span></div>{documents.length ? <div className="question-table">{documents.map((document) => <article key={document.id}><div><b>{document.file_name}</b><span>{document.document_type} · {document.status}</span></div><p>上传时间：{new Date(document.created_at).toLocaleString("zh-CN")}</p>{auth.user.role === "parent" && document.status === "awaiting_confirmation" && <><textarea value={documentDrafts[document.id] ?? "{}"} onChange={(event) => setDocumentDrafts((current) => ({ ...current, [document.id]: event.target.value }))} rows={6} /><button className="primary" disabled={busy} onClick={() => void confirmDocument(document.id)}>确认结构化内容</button></>}</article>)}</div> : <div className="empty-state"><b>暂无资料</b><p>上传后会在这里显示实际处理状态。</p></div>}</article>
        </section>}

        {view === "questions" && auth.user.role === "admin" && <section className="panel"><div className="section-heading"><div><h3>已审核发布题库</h3><p>当前展示第一页，数量使用接口返回的真实总数。</p></div><span>{questionTotal} 题</span></div>{questions.length ? <div className="question-table">{questions.map((question) => <article key={question.id}><div><b>{question.question_code}</b><span>{question.subject} · {question.grade}年级 · 难度{question.difficulty}</span></div><p>{textFromBlocks(question.stem)}</p><em>{question.display_type}</em></article>)}</div> : <div className="empty-state"><b>当前没有已发布题目</b><p>题库发布后，此处会读取实际数据。</p></div>}</section>}
      </main>
    </div>
  );
}
