/**
 * Types that mirror the Chemora backend API contracts (see M20):
 *   POST /api/v1/auth/google   → 200 SessionResponse | 401 generic error
 *   GET  /api/v1/auth/me       → 200 CurrentUser     | 401
 *   POST /api/v1/auth/logout   → 204
 *
 * These are derived from the backend's pydantic response models. The client
 * never invents its own user identity — these shapes are what the backend
 * returns, and the backend remains authoritative.
 */

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface SessionResponse {
  user: CurrentUser;
  session_id: string;
}

export interface ErrorResponse {
  detail: string;
}