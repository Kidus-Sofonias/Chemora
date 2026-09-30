/**
 * M43 student dashboard tests.
 *
 * Drives the full App through the fake backend (same pattern as M28) and asserts
 * the dashboard's empty/new-user state, its deterministic next-lesson
 * recommendation surfaced by the backend, the continue/recent/topic/practice
 * regions, the quick-access rail, error/retry, keyboard/mobile nav, and the
 * dashboard -> Learn hand-off that deep-opens the recommended lesson.
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, test, vi } from 'vitest';
import { App } from '../src/App';
import { ApiClient } from '../src/api/apiClient';
import { ApiAuthService } from '../src/auth/AuthService';
import {
  FakeGoogleProvider,
  installFakeBackend,
  jsonResponse,
  type Handler,
} from './helpers';
import {
  defaultHandler,
  emptyDashboard,
  dashboardWithProgress,
} from './learningShared';

afterEach(() => {
  vi.unstubAllGlobals();
});

async function setupDashboard(handler: Handler) {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler(handler);
  render(<App service={service} provider={provider} api={api} />);
  await screen.findByRole('button', { name: 'Dashboard' });
  await userEvent.setup().click(screen.getByRole('button', { name: 'Dashboard' }));
  return backend;
}

describe('M43: student dashboard', () => {
  test('empty/new-user state shows a recommended first lesson', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, emptyDashboard);
      }
      return defaultHandler(method, url, body);
    });

    await screen.findByTestId('dashboard-empty');
    expect(screen.getByTestId('dashboard-recommended')).toHaveTextContent(
      'Recommended next',
    );
    // The first lesson is unstarted -> the CTA says "Start lesson".
    expect(
      screen.getByTestId('dashboard-recommended-start'),
    ).toHaveTextContent('Start lesson');
    expect(screen.getByTestId('dashboard-topics')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-rail')).toBeInTheDocument();
    // Nothing has been started yet, so the continue/recent lists are absent.
    expect(screen.queryByTestId('dashboard-continue')).toBeNull();
    expect(screen.queryByTestId('dashboard-recent')).toBeNull();
  });

  test('clicking the recommended lesson opens it in Learn', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, emptyDashboard);
      }
      return defaultHandler(method, url, body);
    });

    await userEvent
      .setup()
      .click(screen.getByTestId('dashboard-recommended-start'));
    // The dashboard hands the lesson off to the Learn section, which deep-opens it.
    await screen.findByTestId('section-nav');
    expect(screen.getByRole('button', { name: 'Learn' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  test('an in-progress lesson is the recommended resume target', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, dashboardWithProgress);
      }
      return defaultHandler(method, url, body);
    });

    await screen.findByTestId('dashboard-recommended');
    // ec is in progress -> the CTA resumes it.
    expect(
      screen.getByTestId('dashboard-recommended-start'),
    ).toHaveTextContent('Continue lesson');
    // The empty state is hidden once the user has started something.
    expect(screen.queryByTestId('dashboard-empty')).toBeNull();
    // Continue / recent lists surface the lesson.
    expect(screen.getByTestId('dashboard-continue')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-recent')).toBeInTheDocument();
    const rows = screen.getAllByTestId('dashboard-lesson-electron-configuration');
    expect(rows.length).toBeGreaterThan(0);
    const row = rows[0];
    expect(
      within(row).getByRole('img', { name: '33% complete' }),
    ).toBeInTheDocument();
    expect(
      within(row).getByTestId('needs-review-electron-configuration'),
    ).toHaveTextContent('Needs review');
  });

  test('progress-by-topic and the practice summary reflect server state', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, dashboardWithProgress);
      }
      return defaultHandler(method, url, body);
    });

    const topic = screen.getByTestId('topic-atomic structure');
    expect(topic).toHaveTextContent('33%');
    expect(topic).toHaveTextContent('0/2 lessons');
    // Practice summary rolls up needs-review totals from graded answers.
    expect(screen.getByTestId('practice-needs-review')).toHaveTextContent('1');
  });

  test('the quick-access rail reaches catalog, resume, topics and practice', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, dashboardWithProgress);
      }
      return defaultHandler(method, url, body);
    });

    const rail = screen.getByTestId('dashboard-rail');
    expect(rail).toHaveTextContent('Lessons catalog');
    expect(rail).toHaveTextContent('Continue recommended');
    expect(rail).toHaveTextContent('Progress by topic');
    expect(rail).toHaveTextContent('Practice results');
  });

  test('a server error is surfaced distinctly and can be retried', async () => {
    const backend = await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(500, {
          detail: { code: 'dashboard_error', message: 'boom' },
        });
      }
      return defaultHandler(method, url, body);
    });

    expect(screen.getByTestId('dashboard-error')).toHaveTextContent(
      'Something went wrong',
    );
    backend.setHandler((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, emptyDashboard);
      }
      return defaultHandler(method, url, body);
    });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByTestId('dashboard-empty');
  });

  test('a network failure is distinguishable and recoverable', async () => {
    let offline = true;
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        if (offline) {
          throw new Error('Failed to fetch');
        }
        return jsonResponse(200, emptyDashboard);
      }
      return defaultHandler(method, url, body);
    });

    expect(screen.getByTestId('dashboard-error')).toHaveTextContent(
      'Connection problem',
    );
    offline = false;
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByTestId('dashboard-empty');
  });

  test('the section nav exposes a keyboard-reachable Dashboard button', async () => {
    await setupDashboard((method, url, body) => {
      if (url.endsWith('/learning/dashboard')) {
        return jsonResponse(200, emptyDashboard);
      }
      return defaultHandler(method, url, body);
    });

    const nav = screen.getByRole('navigation', { name: 'Explore sections' });
    expect(
      within(nav).getByRole('button', { name: 'Dashboard' }),
    ).toHaveAttribute('aria-pressed', 'true');
    // The quick-access rail is labeled for assistive technology.
    expect(screen.getByTestId('dashboard-rail')).toHaveAccessibleName(
      'Quick access',
    );
    // Landmark structure: one top-level dashboard heading.
    expect(
      screen.getByRole('heading', { name: 'My Dashboard', level: 1 }),
    ).toBeInTheDocument();
  });
});
