import { vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';
import { ApiClient } from '../src/api/apiClient';
import { ApiAuthService } from '../src/auth/AuthService';
import {
  fakeUser,
  FakeGoogleProvider,
  installFakeBackend,
  jsonResponse,
  noContentResponse,
  type FakeBackend,
} from './helpers';

/**
 * Builds the app with a scriptable backend and a fake Google provider, but
 * does NOT render yet — tests configure the backend handler first so the app's
 * initial GET /auth/me hits the intended handler, then call `renderApp()`.
 */
function createApp() {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  const renderApp = () => render(<App service={service} provider={provider} />);
  return { backend, provider, renderApp };
}

function route(requests: FakeBackend['requests'], suffix: string) {
  return requests.filter((r) => r.url.endsWith(suffix));
}

describe('Auth integration (web)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('shows loading then unauthenticated when there is no session', async () => {
    const { backend, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(401, { detail: 'Not authenticated' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    // Authenticated content is not shown before the check completes.
    expect(screen.queryByText(/Welcome/)).toBeNull();

    await screen.findByTestId('google-sign-in-host');
    expect(screen.queryByText(/Welcome/)).toBeNull();
  });

  test('shows authenticated app when /auth/me returns a user', async () => {
    const { backend, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByText(/Welcome, Ada Lovelace/);
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign out/ })).toBeInTheDocument();
  });

  test('successful login sends the Google credential and then fetches the current user', async () => {
    const { backend, provider, renderApp } = createApp();
    let loggedIn = false;
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/google')) {
        loggedIn = true;
        return jsonResponse(200, { user: fakeUser, session_id: 'sess-1' });
      }
      if (url.endsWith('/auth/me')) {
        return loggedIn ? jsonResponse(200, fakeUser) : jsonResponse(401, { detail: 'Not authenticated' });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByTestId('google-sign-in-host');

    await act(async () => {
      provider.emitCredential('google-id-token-xyz');
    });

    await screen.findByText(/Welcome, Ada Lovelace/);

    const login = route(backend.requests, '/auth/google');
    expect(login.length).toBe(1);
    expect(login[0].body).toEqual({ credential: 'google-id-token-xyz' });
    // After establishing the session, the client fetched the authoritative user.
    await waitFor(() => {
      expect(route(backend.requests, '/auth/me').length).toBeGreaterThanOrEqual(2);
    });
  });

  test('failed login shows a user-facing error and stays unauthenticated', async () => {
    const { backend, provider, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(401, { detail: 'Not authenticated' });
      if (url.endsWith('/auth/google')) return jsonResponse(401, { detail: 'Invalid authentication credential' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByTestId('google-sign-in-host');
    await act(async () => {
      provider.emitCredential();
    });

    await screen.findByRole('alert');
    expect(screen.queryByText(/Welcome/)).toBeNull();
    expect(screen.getByTestId('google-sign-in-host')).toBeInTheDocument();
  });

  test('a network failure during login is not treated as an authenticated session', async () => {
    const { backend, provider, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(401, { detail: 'Not authenticated' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByTestId('google-sign-in-host');

    backend.failNextRequestOnce(); // /auth/google fails at the transport layer
    await act(async () => {
      provider.emitCredential();
    });

    await screen.findByRole('alert');
    expect(screen.queryByText(/Welcome/)).toBeNull();
  });

  test('a network failure during the session check shows an error + retry, not unauthenticated', async () => {
    const { backend, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });
    backend.failNextRequestOnce(); // initial /auth/me fails (offline)
    renderApp();

    await screen.findByText(/Cannot reach the Chemora server/);
    expect(screen.queryByText(/Welcome/)).toBeNull();
    expect(screen.queryByTestId('google-sign-in-host')).toBeNull();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Try again/ }));

    await screen.findByText(/Welcome, Ada Lovelace/);
  });

  test('logout calls the backend and clears the authenticated state', async () => {
    const { backend, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/auth/logout')) return noContentResponse();
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByText(/Welcome, Ada Lovelace/);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Sign out/ }));

    await screen.findByTestId('google-sign-in-host');
    expect(screen.queryByText(/Welcome/)).toBeNull();
    await waitFor(() => {
      expect(route(backend.requests, '/auth/logout').length).toBe(1);
    });
  });

  test('logout clears local state even when the backend call fails', async () => {
    const { backend, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/auth/logout')) return jsonResponse(500, { detail: 'boom' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByText(/Welcome, Ada Lovelace/);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Sign out/ }));

    await screen.findByTestId('google-sign-in-host');
    expect(screen.queryByText(/Welcome/)).toBeNull();
  });

  test('prevents authenticated UI before the auth check completes', async () => {
    const { backend, renderApp } = createApp();
    let resolveMe: (v: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveMe = resolve;
    });
    let nowLoggedIn = false;
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) {
        return nowLoggedIn ? jsonResponse(200, fakeUser) : pending;
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    // While the /auth/me check is still pending, only the loading screen is shown.
    expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
    expect(screen.queryByText(/Welcome/)).toBeNull();
    expect(screen.queryByTestId('google-sign-in-host')).toBeNull();

    nowLoggedIn = true;
    resolveMe!(jsonResponse(200, fakeUser));
    await screen.findByText(/Welcome, Ada Lovelace/);
  });

  test('does not retry authentication after a 401 (no infinite loop)', async () => {
    const { backend, provider, renderApp } = createApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(401, { detail: 'Not authenticated' });
      if (url.endsWith('/auth/google')) return jsonResponse(401, { detail: 'Invalid authentication credential' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp();

    await screen.findByTestId('google-sign-in-host');
    await act(async () => {
      provider.emitCredential();
    });

    await screen.findByRole('alert');

    // Failures must not trigger retry loops: exactly one /auth/me call so far.
    await waitFor(() => {
      expect(route(backend.requests, '/auth/me').length).toBe(1);
    });
    await new Promise((r) => setTimeout(r, 100));
    expect(route(backend.requests, '/auth/me').length).toBe(1);
  });

});