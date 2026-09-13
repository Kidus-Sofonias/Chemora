import { vi } from 'vitest';
import type { CurrentUser } from '../src/api/types';
import type { GoogleSignInProvider } from '../src/auth/googleSignIn';

export const fakeUser: CurrentUser = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'ada@example.com',
  display_name: 'Ada Lovelace',
  avatar_url: null,
  created_at: '2026-01-01T00:00:00.000Z',
  last_login_at: '2026-01-01T00:00:00.000Z',
};

export interface RecordedRequest {
  method: string;
  url: string;
  body: unknown;
  credentials: string | null;
}

/** Returns a minimal Response-compatible object (only what ApiClient uses). */
export function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    async text(): Promise<string> {
      return typeof body === 'string' ? body : JSON.stringify(body);
    },
  } as unknown as Response;
}

export function noContentResponse(): Response {
  return {
    status: 204,
    ok: true,
    async text(): Promise<string> {
      return '';
    },
  } as unknown as Response;
}

export type Handler = (
  method: string,
  url: string,
  body: unknown,
) => Response | PromiseLike<Response>;

export interface FakeBackend {
  requests: RecordedRequest[];
  setHandler(handler: Handler): void;
  /** Make the very next request fail at the transport layer (like offline). */
  failNextRequestOnce(): void;
  restore(): void;
}

function parseBody(body: unknown): unknown {
  if (typeof body !== 'string') return body;
  try {
    return JSON.parse(body) as unknown;
  } catch {
    return body;
  }
}

/**
 * Installs a fake `fetch` so the REAL ApiClient/AuthService run against a
 * scriptable backend. Also records every request for assertions.
 */
export function installFakeBackend(): FakeBackend {
  const requests: RecordedRequest[] = [];
  let handler: Handler | null = null;
  let networkOnce = false;

  const fetchMock = vi.fn(
    async (input: unknown, init: Record<string, unknown> | undefined) => {
      const url =
        typeof input === 'string'
          ? input
          : String((input as { url?: string }).url ?? input);
      const method = (init?.method as string | undefined ?? 'GET').toUpperCase();
      const body = parseBody(init?.body);
      const credentials = init?.credentials as string | null | undefined;
      requests.push({ method, url, body, credentials: credentials ?? null });

      if (networkOnce) {
        networkOnce = false;
        throw new TypeError('Failed to fetch');
      }
      if (!handler) {
        throw new Error('No backend handler installed for this test.');
      }
      return handler(method, url, body);
    },
  );

  vi.stubGlobal('fetch', fetchMock);

  return {
    requests,
    setHandler(h: Handler) {
      handler = h;
    },
    failNextRequestOnce() {
      networkOnce = true;
    },
    restore() {
      vi.unstubAllGlobals();
    },
  };
}

/** Fake Google provider: never contacts Google. Emits a credential on demand. */
export class FakeGoogleProvider implements GoogleSignInProvider {
  clientId: string | null = 'test-client.apps.googleusercontent.com';
  private onCredential: ((credential: string) => void) | null = null;

  attach(_host: HTMLElement, onCredential: (credential: string) => void): void {
    this.onCredential = onCredential;
  }

  emitCredential(token = 'google-id-token-abc123'): void {
    if (this.onCredential) {
      this.onCredential(token);
    }
  }
}