export type User = {
  id: string;
  email: string;
  role: "parent" | "student" | "admin";
  display_name: string;
  status: string;
};

export type AuthData = {
  access_token: string;
  token_type: string;
  user: User;
  family_id: string | null;
  refresh_token?: string;
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
    const parsed = JSON.parse(value) as AuthData;
    if (!parsed.access_token || !parsed.user) throw new Error("invalid auth");
    if (localStorage.getItem(STORAGE_KEY)) {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.setItem(STORAGE_KEY, value);
    }
    return parsed;
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

async function parseError(response: Response): Promise<Error> {
  let payload: ApiErrorEnvelope = {};
  try {
    payload = (await response.json()) as ApiErrorEnvelope;
  } catch {
    // Keep a user-safe fallback below.
  }
  const message = payload.error?.message ?? `请求失败（${response.status}）`;
  const requestId = payload.error?.request_id ? `，请求号 ${payload.error.request_id}` : "";
  return new Error(`${message}${requestId}`);
}

async function refreshAccessToken(): Promise<AuthData | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include"
    })
      .then(async (response) => {
        if (!response.ok) {
          storeAuth(null);
          window.dispatchEvent(new Event("xueji-auth-expired"));
          return null;
        }
        const payload = (await response.json()) as ApiEnvelope<AuthData>;
        storeAuth(payload.data);
        window.dispatchEvent(new CustomEvent<AuthData>("xueji-auth-updated", { detail: payload.data }));
        return payload.data;
      })
      .catch(() => {
        storeAuth(null);
        window.dispatchEvent(new Event("xueji-auth-expired"));
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  auth: AuthData | null = getStoredAuth(),
  retryAfterRefresh = true
): Promise<ApiEnvelope<T>> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (auth?.access_token) headers.set("Authorization", `Bearer ${auth.access_token}`);
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  if (response.status === 401 && auth && retryAfterRefresh && path !== "/auth/refresh") {
    const refreshed = await refreshAccessToken();
    if (refreshed) return api<T>(path, options, refreshed, false);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return { data: undefined as T, meta: {} };
  return (await response.json()) as ApiEnvelope<T>;
}

export async function apiBlob(
  path: string,
  auth: AuthData | null = getStoredAuth(),
  retryAfterRefresh = true
): Promise<Blob> {
  const headers = new Headers();
  if (auth?.access_token) headers.set("Authorization", `Bearer ${auth.access_token}`);
  const response = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  if (response.status === 401 && auth && retryAfterRefresh) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiBlob(path, refreshed, false);
  }
  if (!response.ok) throw await parseError(response);
  return response.blob();
}
