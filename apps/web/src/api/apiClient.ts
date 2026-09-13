import type { CurrentUser, ErrorResponse, SessionResponse } from './types';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

/**
 * Resolve the Chemora backend base URL from configuration.
 * Frontend environment variables are public (not secrets).
 * A trailing slash is stripped for consistent URL building.
 */
export function resolveApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const url = typeof raw === 'string' ? raw.trim() : '';
  return url ? url.replace(/\/+$/, '') : DEFAULT_API_BASE_URL;
}

/**
 * A typed error surfaced by the API client.
 * - `status` is the HTTP status code when the backend responded.
 * - `status` is `null` when the request failed before an HTTP response
 *   (network unavailable, timeout, DNS failure, backend down).
 */
export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  /** True when the backend rejected the request as unauthenticated. */
  get isAuthError(): boolean {
    return this.status === 401;
  }

  /** True when the request never reached the backend (no HTTP response). */
  get isNetworkError(): boolean {
    return this.status === null;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
}

/**
 * Centralized API client. All authentication requests go through this client
 * so that base URL, credentials handling, JSON encoding, and error
 * classification live in exactly one place.
 */
export class ApiClient {
  readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? resolveApiBaseUrl();
  }

  /** POST /api/v1/auth/google — exchange a Google credential for a Chemora session. */
  async googleLogin(credential: string): Promise<SessionResponse> {
    return this.request<SessionResponse>('/api/v1/auth/google', {
      method: 'POST',
      body: { credential },
    });
  }

  /** GET /api/v1/auth/me — the backend is the source of truth for the user. */
  async getCurrentUser(): Promise<CurrentUser> {
    return this.request<CurrentUser>('/api/v1/auth/me');
  }

  /** POST /api/v1/auth/logout — revoke the server-side session. */
  async logout(): Promise<void> {
    await this.request<unknown>('/api/v1/auth/logout', { method: 'POST' });
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    let response: Response;
    try {
      response = await fetch(this.baseUrl + path, {
        method: options.method ?? 'GET',
        headers:
          options.body === undefined
            ? undefined
            : { 'Content-Type': 'application/json' },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        // Send/receive the HttpOnly session cookie. The browser manages the
        // cookie; JavaScript never reads its value.
        credentials: 'include',
      });
    } catch {
      // Transport-level failure — the backend never answered.
      throw new ApiError(
        'Could not reach the Chemora server. Check your connection and try again.',
        null,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }

    if (!response.ok) {
      const detail = readDetail(data);
      throw new ApiError(
        detail ?? `Request failed (${response.status}).`,
        response.status,
      );
    }

    return data as T;
  }
}

function readDetail(data: unknown): string | null {
  if (typeof data !== 'object' || data === null) return null;
  const detail = (data as ErrorResponse).detail;
  return typeof detail === 'string' && detail ? detail : null;
}