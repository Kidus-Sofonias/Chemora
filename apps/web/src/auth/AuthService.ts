import type { CurrentUser } from '../api/types';
import { ApiClient } from '../api/apiClient';

/**
 * The authoritative user-identity boundary used by the client.
 */
export interface AuthService {
  /** GET /auth/me — the current Chemora user, as reported by the backend. */
  getCurrentUser(): Promise<CurrentUser>;
  /** Exchange a Google ID-token credential for a Chemora session + user. */
  exchangeCredential(credential: string): Promise<CurrentUser>;
  /** POST /auth/logout — revoke the server-side session. */
  signOut(): Promise<void>;
}

/**
 * Production AuthService. It depends only on the API client; all identity and
 * session decisions come from the backend.
 */
export class ApiAuthService implements AuthService {
  constructor(private readonly api: ApiClient) {}

  async getCurrentUser(): Promise<CurrentUser> {
    return this.api.getCurrentUser();
  }

  async exchangeCredential(credential: string): Promise<CurrentUser> {
    // 1) Establish a Chemora session with the backend (the credential is
    //    verified server-side).
    // 2) Fetch the authoritative current user. This also proves the session
    //    cookie was actually accepted — if /auth/me returns 401, we never
    //    report the user as authenticated just because Google succeeded.
    await this.api.googleLogin(credential);
    return this.api.getCurrentUser();
  }

  async signOut(): Promise<void> {
    await this.api.logout();
  }
}