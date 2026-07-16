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

export type ApiEnvelope<T> = { data: T; meta: Record<string, unknown> };
type ApiErrorEnvelope = { error?: { code?: string; message?: string; request_id?: string } };

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
const STORAGE_KEY = "xueji-auth";
let refreshPromise: Promise<AuthData | null> | null = null;

export function getStoredAuth(): AuthData | null {
  const value = sessionStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(STORAGE_KEY);
  if (!value) return null;
  try {
    const auth = JSON.parse(value) as AuthData;
    if (localStorage.getItem(STORAGE_KEY)) {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.setItem(STORAGE_KEY, value);
    }
    return auth;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function storeAuth(auth: AuthData | null): void {
  localStorage.removeItem(STORAGE_KEY);
  if (auth) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  else sessionStorage.removeItem(STORAGE_KEY);
}

async function refreshAuth(auth: AuthData): Promise<AuthData | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: auth.refresh_token })
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const payload = (await response.json()) as ApiEnvelope<AuthData>;
        storeAuth(payload.data);
        return payload.data;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function request(
  path: string,
  options: RequestInit,
  auth: AuthData | null
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (auth?.access_token) headers.set("Authorization", `Bearer ${auth.access_token}`);
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  auth: AuthData | null = getStoredAuth()
): Promise<ApiEnvelope<T>> {
  let activeAuth = getStoredAuth() ?? auth;
  let response = await request(path, options, activeAuth);

  const canRefresh = response.status === 401 && activeAuth?.refresh_token && path !== "/auth/refresh";
  if (canRefresh) {
    activeAuth = await refreshAuth(activeAuth);
    if (activeAuth) response = await request(path, options, activeAuth);
    else storeAuth(null);
  }

  if (!response.ok) {
    let payload: ApiErrorEnvelope = {};
    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      // Keep a user-safe fallback below.
    }
    if (response.status === 401) storeAuth(null);
    const message = payload.error?.message ?? `请求失败（${response.status}）`;
    const requestId = payload.error?.request_id ? `，请求号 ${payload.error.request_id}` : "";
    throw new Error(`${message}${requestId}`);
  }
  if (response.status === 204) return { data: undefined as T, meta: {} };
  return (await response.json()) as ApiEnvelope<T>;
}
