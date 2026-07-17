import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, AuthData, getStoredAuth, storeAuth } from "./api";

type Policy = {
  terms_version: string;
  privacy_version: string;
  child_policy_version: string;
  required_scope: Record<string, boolean>;
};

type Consent = {
  id: string;
  terms_version: string;
  privacy_version: string;
  child_policy_version: string;
  consent_scope: Record<string, boolean>;
  accepted_at: string;
  revoked_at: string | null;
};

type Session = {
  id: string;
  expires_at: string;
  revoked_at: string | null;
  user_agent: string | null;
  created_at: string;
};

const panelStyle: React.CSSProperties = {
  position: "fixed",
  right: 24,
  bottom: 76,
  width: "min(460px, calc(100vw - 32px))",
  maxHeight: "78vh",
  overflowY: "auto",
  background: "#fff",
  border: "1px solid #dce3f0",
  borderRadius: 18,
  boxShadow: "0 18px 60px rgba(20, 32, 70, .24)",
  padding: 20,
  zIndex: 1000
};

const fieldStyle: React.CSSProperties = { display: "grid", gap: 6, marginBottom: 12 };
const inputStyle: React.CSSProperties = { border: "1px solid #cfd7e6", borderRadius: 10, padding: "10px 12px" };
const buttonStyle: React.CSSProperties = { border: 0, borderRadius: 10, padding: "10px 14px", cursor: "pointer" };

export default function GlobalAccountCenter() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [open, setOpen] = useState(false);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [consents, setConsents] = useState<Consent[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

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
    if (!auth) return;
    setBusy(true);
    setMessage("");
    try {
      const sessionResponse = await api<Session[]>("/account/sessions", {}, auth);
      setSessions(sessionResponse.data);
      if (auth.user.role === "parent") {
        const [policyResponse, consentResponse] = await Promise.all([
          api<Policy>("/legal/current", {}, null),
          api<Consent[]>("/legal/consents", {}, auth)
        ]);
        setPolicy(policyResponse.data);
        setConsents(consentResponse.data);
      } else {
        setPolicy(null);
        setConsents([]);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号信息加载失败");
    } finally {
      setBusy(false);
    }
  }, [auth]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function acceptConsent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth || !policy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api(
        "/legal/consents",
        {
          method: "POST",
          body: JSON.stringify({
            terms_version: policy.terms_version,
            privacy_version: policy.privacy_version,
            child_policy_version: policy.child_policy_version,
            consent_scope: {
              student_profile: form.get("student_profile") === "on",
              practice_records: form.get("practice_records") === "on",
              learning_documents: form.get("learning_documents") === "on",
              automated_analysis: form.get("automated_analysis") === "on"
            }
          })
        },
        auth
      );
      setMessage("监护人授权已记录，后续变更会保留版本和时间记录。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "授权提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api(
        "/account/password",
        {
          method: "POST",
          body: JSON.stringify({
            current_password: form.get("current_password"),
            new_password: form.get("new_password"),
            revoke_other_sessions: true
          })
        },
        auth
      );
      storeAuth(null);
      setAuth(null);
      setOpen(false);
      window.dispatchEvent(new Event("xueji-auth-expired"));
      setMessage("密码已修改，请重新登录。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "密码修改失败");
    } finally {
      setBusy(false);
    }
  }

  async function revokeSession(sessionId: string) {
    if (!auth) return;
    setBusy(true);
    try {
      await api(`/account/sessions/${sessionId}`, { method: "DELETE" }, auth);
      setMessage("登录会话已撤销。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "会话撤销失败");
    } finally {
      setBusy(false);
    }
  }

  async function deactivateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api(
        "/account/deactivate",
        {
          method: "POST",
          body: JSON.stringify({ password: form.get("password"), confirmation: form.get("confirmation") })
        },
        auth
      );
      storeAuth(null);
      setAuth(null);
      setOpen(false);
      window.dispatchEvent(new Event("xueji-auth-expired"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号停用失败");
    } finally {
      setBusy(false);
    }
  }

  if (!auth) return null;
  const activeConsent = consents.find((item) => !item.revoked_at);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        style={{ ...buttonStyle, position: "fixed", right: 24, bottom: 24, background: "#253a84", color: "#fff", zIndex: 1001 }}
      >
        账号与授权
      </button>
      {open && (
        <aside style={panelStyle} aria-label="账号与授权中心">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div><strong style={{ fontSize: 20 }}>账号与授权</strong><div style={{ color: "#647089", marginTop: 4 }}>{auth.user.email}</div></div>
            <button type="button" onClick={() => setOpen(false)} style={{ ...buttonStyle, background: "#eef1f7" }}>关闭</button>
          </div>

          {message && <p style={{ background: "#eef4ff", borderRadius: 10, padding: 10 }}>{message}</p>}

          {auth.user.role === "parent" && policy && (
            <section style={{ marginTop: 20 }}>
              <h3>监护人授权</h3>
              {activeConsent ? (
                <div style={{ background: "#effaf3", borderRadius: 12, padding: 12 }}>
                  <b>授权有效</b>
                  <p style={{ marginBottom: 0 }}>确认时间：{new Date(activeConsent.accepted_at).toLocaleString("zh-CN")}</p>
                  <small>儿童规则版本：{activeConsent.child_policy_version}</small>
                </div>
              ) : (
                <form onSubmit={acceptConsent}>
                  <p>创建学生档案、练习和上传学习资料前，需要由监护人明确确认处理范围。</p>
                  <label style={fieldStyle}><span><input name="student_profile" type="checkbox" required /> 允许保存学生基础档案</span></label>
                  <label style={fieldStyle}><span><input name="practice_records" type="checkbox" required /> 允许保存练习、作答和错题记录</span></label>
                  <label style={fieldStyle}><span><input name="learning_documents" type="checkbox" required /> 允许保存上传的成绩与评语资料</span></label>
                  <label style={fieldStyle}><span><input name="automated_analysis" type="checkbox" /> 允许在真实AI能力上线后进行自动分析（当前未启用）</span></label>
                  <small>条款 {policy.terms_version} · 隐私政策 {policy.privacy_version} · 儿童规则 {policy.child_policy_version}</small>
                  <button type="submit" disabled={busy} style={{ ...buttonStyle, display: "block", marginTop: 12, background: "#253a84", color: "#fff" }}>确认并记录授权</button>
                </form>
              )}
            </section>
          )}

          <section style={{ marginTop: 22 }}>
            <h3>修改密码</h3>
            <form onSubmit={changePassword}>
              <label style={fieldStyle}>当前密码<input name="current_password" type="password" minLength={8} required style={inputStyle} /></label>
              <label style={fieldStyle}>新密码<input name="new_password" type="password" minLength={10} required style={inputStyle} /></label>
              <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#253a84", color: "#fff" }}>修改密码并退出其他会话</button>
            </form>
          </section>

          <section style={{ marginTop: 22 }}>
            <h3>登录会话</h3>
            {sessions.length ? sessions.map((session) => (
              <article key={session.id} style={{ borderTop: "1px solid #e5e9f1", padding: "10px 0" }}>
                <b>{session.revoked_at ? "已撤销" : "有效会话"}</b>
                <div style={{ color: "#647089", fontSize: 13 }}>{session.user_agent || "未知设备"}</div>
                <small>创建：{new Date(session.created_at).toLocaleString("zh-CN")}</small>
                {!session.revoked_at && <button type="button" disabled={busy} onClick={() => void revokeSession(session.id)} style={{ ...buttonStyle, marginLeft: 8, background: "#eef1f7" }}>撤销</button>}
              </article>
            )) : <p>当前没有登录会话记录。</p>}
          </section>

          <details style={{ marginTop: 22 }}>
            <summary style={{ cursor: "pointer", color: "#a22" }}>停用账号</summary>
            <form onSubmit={deactivateAccount} style={{ marginTop: 12 }}>
              <label style={fieldStyle}>当前密码<input name="password" type="password" required style={inputStyle} /></label>
              <label style={fieldStyle}>输入“停用我的账号”确认<input name="confirmation" required style={inputStyle} /></label>
              <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#a22", color: "#fff" }}>停用账号</button>
            </form>
          </details>
        </aside>
      )}
    </>
  );
}
