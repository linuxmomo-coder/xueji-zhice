import { CSSProperties, FormEvent, useCallback, useEffect, useState } from "react";
import { api, AuthData, getStoredAuth } from "./api";

type VerificationStatus = {
  required: boolean;
  verified: boolean;
  email: string;
};

const panelStyle: CSSProperties = {
  position: "fixed",
  left: 24,
  bottom: 76,
  width: "min(430px, calc(100vw - 32px))",
  background: "#fff",
  border: "1px solid #dce3f0",
  borderRadius: 18,
  boxShadow: "0 18px 60px rgba(20, 32, 70, .24)",
  padding: 20,
  zIndex: 1000
};
const inputStyle: CSSProperties = {
  border: "1px solid #cfd7e6",
  borderRadius: 10,
  padding: "10px 12px",
  width: "100%",
  boxSizing: "border-box"
};
const buttonStyle: CSSProperties = {
  border: 0,
  borderRadius: 10,
  padding: "10px 14px",
  cursor: "pointer"
};

function removeRecoveryQuery(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("verify_email_token");
  url.searchParams.delete("password_reset_token");
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

export default function GlobalRecoveryCenter() {
  const [auth, setAuth] = useState<AuthData | null>(() => getStoredAuth());
  const [verification, setVerification] = useState<VerificationStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const params = new URLSearchParams(window.location.search);
  const [verificationToken, setVerificationToken] = useState(params.get("verify_email_token") ?? "");
  const [resetToken, setResetToken] = useState(params.get("password_reset_token") ?? "");

  useEffect(() => {
    const sync = () => setAuth(getStoredAuth());
    window.addEventListener("xueji-auth-updated", sync);
    window.addEventListener("xueji-auth-expired", sync);
    return () => {
      window.removeEventListener("xueji-auth-updated", sync);
      window.removeEventListener("xueji-auth-expired", sync);
    };
  }, []);

  const loadVerification = useCallback(async () => {
    if (!auth) {
      setVerification(null);
      return;
    }
    try {
      const response = await api<VerificationStatus>("/auth/email-verification/status", {}, auth);
      setVerification(response.data);
    } catch {
      setVerification(null);
    }
  }, [auth]);

  useEffect(() => {
    void loadVerification();
  }, [loadVerification]);

  useEffect(() => {
    if (verificationToken || resetToken) setOpen(true);
  }, [verificationToken, resetToken]);

  async function confirmEmail() {
    if (!verificationToken) return;
    setBusy(true);
    setMessage("");
    try {
      await api("/auth/email-verification/confirm", {
        method: "POST",
        body: JSON.stringify({ token: verificationToken })
      }, null);
      setMessage("邮箱验证成功，可以继续使用受保护功能。");
      setVerificationToken("");
      removeRecoveryQuery();
      await loadVerification();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "邮箱验证失败");
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    if (!auth) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await api<{ already_verified: boolean; delivery: string }>(
        "/auth/email-verification/request",
        { method: "POST" },
        auth
      );
      setMessage(response.data.already_verified ? "邮箱已经完成验证。" : "验证邮件已受理，请检查邮箱。");
      await loadVerification();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "验证邮件发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function requestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setMessage("");
    try {
      await api("/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email") })
      }, null);
      setMessage("请求已受理。账号存在时，系统会发送密码重置邮件。");
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "密码重置请求失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirmReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resetToken) return;
    const form = new FormData(event.currentTarget);
    const first = String(form.get("new_password") ?? "");
    const second = String(form.get("confirm_password") ?? "");
    if (first !== second) {
      setMessage("两次输入的新密码不一致。");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token: resetToken, new_password: first })
      }, null);
      setMessage("密码已重置，请使用新密码登录。");
      setResetToken("");
      removeRecoveryQuery();
      event.currentTarget.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "密码重置失败");
    } finally {
      setBusy(false);
    }
  }

  const needsVerification = Boolean(auth && verification?.required && !verification.verified);
  if (auth && !needsVerification && !verificationToken && !resetToken && !open) return null;

  return (
    <>
      {!auth && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{ ...buttonStyle, position: "fixed", left: 24, bottom: 24, background: "#fff", color: "#253a84", border: "1px solid #cfd7e6", zIndex: 1001 }}
        >
          忘记密码
        </button>
      )}
      {needsVerification && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{ ...buttonStyle, position: "fixed", left: 24, bottom: 24, background: "#a44b00", color: "#fff", zIndex: 1001 }}
        >
          邮箱尚未验证
        </button>
      )}
      {open && (
        <aside style={panelStyle} aria-label="邮箱验证与密码恢复">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div><strong style={{ fontSize: 20 }}>安全验证</strong><div style={{ color: "#647089", marginTop: 4 }}>邮箱验证与密码恢复</div></div>
            <button type="button" onClick={() => setOpen(false)} style={{ ...buttonStyle, background: "#eef1f7" }}>关闭</button>
          </div>

          {message && <p style={{ background: "#eef4ff", borderRadius: 10, padding: 10 }}>{message}</p>}

          {verificationToken && (
            <section style={{ marginTop: 18 }}>
              <h3>确认邮箱</h3>
              <p>点击后将验证该一次性链接。链接只能使用一次。</p>
              <button type="button" disabled={busy} onClick={() => void confirmEmail()} style={{ ...buttonStyle, background: "#253a84", color: "#fff" }}>完成邮箱验证</button>
            </section>
          )}

          {auth && verification && (
            <section style={{ marginTop: 18 }}>
              <h3>邮箱状态</h3>
              <p>{verification.email} · {verification.verified ? "已验证" : "未验证"}</p>
              {!verification.verified && <button type="button" disabled={busy} onClick={() => void resendVerification()} style={{ ...buttonStyle, background: "#253a84", color: "#fff" }}>重新发送验证邮件</button>}
            </section>
          )}

          {resetToken ? (
            <section style={{ marginTop: 18 }}>
              <h3>设置新密码</h3>
              <form onSubmit={confirmReset}>
                <label style={{ display: "grid", gap: 6, marginBottom: 12 }}>新密码<input name="new_password" type="password" minLength={10} maxLength={128} required style={inputStyle} /></label>
                <label style={{ display: "grid", gap: 6, marginBottom: 12 }}>再次输入<input name="confirm_password" type="password" minLength={10} maxLength={128} required style={inputStyle} /></label>
                <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#253a84", color: "#fff" }}>确认重置密码</button>
              </form>
            </section>
          ) : !auth && !verificationToken && (
            <section style={{ marginTop: 18 }}>
              <h3>忘记密码</h3>
              <p>系统不会透露该邮箱是否注册。</p>
              <form onSubmit={requestReset}>
                <label style={{ display: "grid", gap: 6, marginBottom: 12 }}>账号邮箱<input name="email" type="email" required style={inputStyle} /></label>
                <button type="submit" disabled={busy} style={{ ...buttonStyle, background: "#253a84", color: "#fff" }}>发送重置邮件</button>
              </form>
            </section>
          )}
        </aside>
      )}
    </>
  );
}
