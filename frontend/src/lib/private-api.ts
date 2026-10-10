import type { User } from "firebase/auth";

const baseUrl = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export class PrivateApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function privateApi<T = void>(user: User, path: string, method: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  for (let attempt = 0; attempt < 2; attempt++) {
    let token: string;
    try { token = await user.getIdToken(attempt === 1); }
    catch { throw new PrivateApiError(401, "Sign in again to enable cloud alerts."); }
    const response = await fetch(`${baseUrl}/api${path}`, {
      method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(8000)]) : AbortSignal.timeout(8000),
      cache: "no-store",
    });
    if (response.status === 401 && attempt === 0) continue;
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new PrivateApiError(response.status, typeof payload?.detail === "string" ? payload.detail : "Cloud alerts could not connect. In-app directions are still available.");
    }
    return response.status === 204 ? undefined as T : response.json();
  }
  throw new PrivateApiError(401, "Sign in again to enable cloud alerts.");
}
