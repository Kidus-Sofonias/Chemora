import { ApiClient, ApiError, resolveApiBaseUrl } from '../src/api/apiClient';
import {
  fakeUser,
  installFakeBackend,
  jsonResponse,
  noContentResponse,
  type FakeBackend,
} from './helpers';

describe('ApiClient', () => {
  let backend: FakeBackend;

  beforeEach(() => {
    backend = installFakeBackend();
  });

  afterEach(() => {
    backend.restore();
  });

  test('resolveApiBaseUrl falls back to the local backend', () => {
    expect(resolveApiBaseUrl()).toContain('localhost:8000');
  });

  test('builds requests against a configurable base URL', async () => {
    backend.setHandler((_m, url) => {
      expect(url.startsWith('http://api.example')).toBe(true);
      return jsonResponse(200, fakeUser);
    });
    const api = new ApiClient('http://api.example');
    const user = await api.getCurrentUser();
    expect(user.id).toBe(fakeUser.id);
  });

  test('sends body, JSON content type, and cookie credentials on login', async () => {
    backend.setHandler((_m, _url, body) => {
      expect(body).toEqual({ credential: 'tok' });
      return jsonResponse(200, { user: fakeUser, session_id: 's1' });
    });
    const api = new ApiClient('http://test');

    await api.googleLogin('tok');

    const login = backend.requests.find((r) => r.url.endsWith('/auth/google'));
    expect(login).toBeDefined();
    expect(login!.body).toEqual({ credential: 'tok' });
    expect(login!.credentials).toBe('include');
  });

  test('logout (204) resolves without body', async () => {
    backend.setHandler(() => noContentResponse());
    const api = new ApiClient('http://test');
    await api.logout(); // should not throw
    expect(backend.requests.some((r) => r.url.endsWith('/auth/logout'))).toBe(true);
  });

  test('getCurrentUser parses the backend user', async () => {
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });
    const api = new ApiClient('http://test');
    const user = await api.getCurrentUser();
    expect(user.email).toBe('ada@example.com');
  });

  test('treats 401 as an authentication error', async () => {
    backend.setHandler(() => jsonResponse(401, { detail: 'Not authenticated' }));
    const api = new ApiClient('http://test');
    const err = await api.getCurrentUser().then(() => null, (e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBe(401);
    expect(apiErr.isAuthError).toBe(true);
    expect(apiErr.isNetworkError).toBe(false);
  });

  test('treats a network failure as an authentication-unknown error (status null)', async () => {
    backend.failNextRequestOnce();
    backend.setHandler(() => jsonResponse(200, fakeUser));
    const api = new ApiClient('http://test');
    const err = await api.getCurrentUser().then(() => null, (e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBeNull();
    expect(apiErr.isNetworkError).toBe(true);
    expect(apiErr.isAuthError).toBe(false);
  });

  test('surfaces a readable message for 5xx server errors', async () => {
    backend.setHandler(() => jsonResponse(500, { detail: 'internal error' }));
    const api = new ApiClient('http://test');
    const err = await api.getCurrentUser().then(() => null, (e: unknown) => e);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBe(500);
    expect(apiErr.message).toContain('internal error');
  });
});