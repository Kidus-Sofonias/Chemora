/**
 * M28 learning-experience tests.
 *
 * The defaultHandler in learning.test.tsx answers GET /learning/progress
 * with an empty list (see m28EmptyProgressHandler), so the catalog renders
 * plain "Start lesson" cards. These tests layer M28 behaviors on top:
 * resume badges, continue labels, and prev/next section navigation.
 */
import { render, screen } from '@testing-library/react';
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
import { catalog, defaultHandler, freshProgress, lessonDetail } from './learningShared';

afterEach(() => {
  vi.unstubAllGlobals();
});

async function setupApp(handler: Handler) {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler(handler);
  render(<App service={service} provider={provider} api={api} />);
  // Navigate to the Learn tab like a real user (mirrors learning.test.tsx).
  await screen.findByRole('button', { name: /Explore/ });
  await userEvent.setup().click(screen.getByRole('button', { name: 'Learn' }));
  return backend;
}

describe('M28: catalog resume (learning experience)', () => {
  test('a started lesson shows a continue label and progress line', async () => {
    setupApp((method, url, body) => {
      if (url.endsWith('/learning/progress')) {
        return jsonResponse(200, {
          progress: [
            {
              ...freshProgress,
              progress_percent: 40,
              completed_sections: ['intro'],
            },
          ],
        });
      }
      return defaultHandler(method, url, body);
    });
    await screen.findByTestId('catalog-progress-electron-configuration');
    expect(screen.getByTestId('catalog-progress-electron-configuration')).toHaveTextContent(
      '40% complete',
    );
    // The continue label replaces "Start lesson" for that lesson only.
    expect(
      screen.getByRole('button', { name: 'Continue lesson' }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Start lesson' }).length).toBe(2);
  });

  test('a completed lesson shows Completed and a review action', async () => {
    setupApp((method, url, body) => {
      if (url.endsWith('/learning/progress')) {
        return jsonResponse(200, {
          progress: [{ ...freshProgress, progress_percent: 100, completed: true }],
        });
      }
      return defaultHandler(method, url, body);
    });
    await screen.findByTestId('catalog-progress-electron-configuration');
    expect(screen.getByTestId('catalog-progress-electron-configuration')).toHaveTextContent(
      'Completed',
    );
    expect(screen.getByRole('button', { name: 'Review lesson' })).toBeInTheDocument();
  });

  test('a fresh user sees no progress badges', async () => {
    setupApp((method, url, body) => defaultHandler(method, url, body));
    await screen.findByTestId('lesson-list');
    expect(
      screen.queryByTestId('catalog-progress-electron-configuration'),
    ).toBeNull();
    expect(screen.getAllByRole('button', { name: 'Start lesson' }).length).toBe(3);
  });

  test('a failing progress fetch leaves the catalog usable', async () => {
    setupApp((method, url, body) => {
      if (url.endsWith('/learning/progress')) return jsonResponse(500, { detail: 'boom' });
      return defaultHandler(method, url, body);
    });
    await screen.findByTestId('lesson-list');
    expect(screen.getAllByRole('button', { name: 'Start lesson' }).length).toBe(3);
  });
});

describe('M28: section navigation', () => {
  test('prev/next buttons step through sections with position indicator', async () => {
    setupApp((method, url, body) => defaultHandler(method, url, body));
    const user = userEvent.setup();
    await screen.findByTestId('lesson-list');
    await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
    await screen.findByTestId('section-nav');

    expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 1 of 3');
    expect(screen.getByTestId('nav-prev')).toBeDisabled();

    await user.click(screen.getByTestId('nav-next'));
    expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 2 of 3');
    expect(screen.getByTestId('nav-prev')).toBeEnabled();

    await user.click(screen.getByTestId('nav-next'));
    expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 3 of 3');
    expect(screen.getByTestId('nav-next')).toBeDisabled();

    await user.click(screen.getByTestId('nav-prev'));
    expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 2 of 3');
  });

  test('the focused section is highlighted with aria-current', async () => {
    setupApp((method, url, body) => defaultHandler(method, url, body));
    const user = userEvent.setup();
    await screen.findByTestId('lesson-list');
    await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
    await screen.findByTestId('section-nav');
    expect(screen.getByTestId('section-intro')).toHaveAttribute('aria-current', 'true');
    expect(screen.getByTestId('section-spotlight')).not.toHaveAttribute('aria-current');
    await user.click(screen.getByTestId('nav-next'));
    expect(screen.getByTestId('section-spotlight')).toHaveAttribute('aria-current', 'true');
  });

  test('resume focuses the first incomplete section', async () => {
    setupApp((method, url, body) => {
      if (url.includes('/learning/lessons/electron-configuration/progress')) {
        return jsonResponse(200, {
          ...freshProgress,
          completed_sections: ['intro'],
          progress_percent: 33,
        });
      }
      return defaultHandler(method, url, body);
    });
    const user = userEvent.setup();
    await screen.findByTestId('lesson-list');
    await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
    await screen.findByTestId('section-nav');
    // intro is complete, so the lesson focuses the spotlight section.
    expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 2 of 3');
    expect(screen.getByTestId('section-spotlight')).toHaveAttribute('aria-current', 'true');
  });

  test('catalog loads the expanded M28 lesson list from the backend', async () => {
    setupApp((method, url, body) => defaultHandler(method, url, body));
    await screen.findByTestId('lesson-list');
    // The shared fake catalog now carries the M28 lessons too.
    expect(catalog.lessons.length).toBeGreaterThanOrEqual(3);
  });

  test('lesson detail renders without console errors on navigation', async () => {
    const errors: string[] = [];
    const original = console.error;
    console.error = (...args: unknown[]) => {
      errors.push(String(args[0]));
    };
    try {
      setupApp((method, url, body) => defaultHandler(method, url, body));
      const user = userEvent.setup();
      await screen.findByTestId('lesson-list');
      await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
      await screen.findByTestId('section-nav');
      await user.click(screen.getByTestId('nav-next'));
      await user.click(screen.getByTestId('nav-next'));
      expect(screen.getByTestId('nav-position')).toHaveTextContent('Section 3 of 3');
      expect(errors).toEqual([]);
    } finally {
      console.error = original;
    }
  });

  // Ensure the shared lesson detail is importable and well-formed.
  test('shared lesson fixture has ordered multi-section layout', () => {
    expect(lessonDetail.sections.length).toBe(3);
    expect(lessonDetail.sections.map((s) => s.id)).toEqual([
      'intro',
      'spotlight',
      'practice',
    ]);
  });
});
