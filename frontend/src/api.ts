export type User = {
  id: string;
  email: string;
  role: "parent" | "student" | "admin";
  display_name: string;
  status: string;
};

export type AuthData = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  family_id: string | null;
};

type ApiEnvelope<T> = { data: T; meta: Record<string, unknown> };
type ApiErrorEnvelope = { error?: { code?: string; message?: string; request_id?: string } };

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export function getStoredAuth(): AuthData | null {
  const value = localStorage.getItem("xueji-auth");
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthData;
  } catch {
    localStorage.removeItem("xueji-auth");
    return null;
  }
}

export function storeAuth(auth: AuthData | null): void {
  if (auth) localStorage.setItem("xueji-auth", JSON.stringify(auth));
  else localStorage.removeItem("xueji-auth");
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  auth: AuthData | null = getStoredAuth()
): Promise<ApiEnvelope<T>> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (auth?.access_token) headers.set("Authorization", `Bearer ${auth.access_token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let payload: ApiErrorEnvelope = {};
    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      // Keep a user-safe fallback below.
    }
    const message = payload.error?.message ?? `请求失败（${response.status}）`;
    const requestId = payload.error?.request_id ? `，请求号 ${payload.error.request_id}` : "";
    throw new Error(`${message}${requestId}`);
  }
  if (response.status === 204) return { data: undefined as T, meta: {} };
  return (await response.json()) as ApiEnvelope<T>;
}
