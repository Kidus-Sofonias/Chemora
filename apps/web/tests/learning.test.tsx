import { vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';
import { ApiClient } from '../src/api/apiClient';
import { ApiAuthService } from '../src/auth/AuthService';
import {
  fakeUser,
  FakeGoogleProvider,
  installFakeBackend,
  jsonResponse,

  type Handler,
} from './helpers';
import {
  defaultHandler,
  freshProgress,
} from './learningShared';

/**
 * Learning Core (M24) integration tests.
 *
 * The REAL ApiClient/AuthService/pages run against a scripted fake backend —
 * no live server and no real Google account. Shapes mirror the backend
 * Pydantic contracts exactly.
 */





/** M25: a lesson whose spotlight analyses a molecule instead of an element. */

/** Shape mirrors the backend chemistry explore contract (M22). */

async function setupApp(
  handler: Handler = (m, u, b) => defaultHandler(m, u, b),
) {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler(handler);
  render(<App service={service} provider={provider} api={api} />);
  await screen.findByRole('button', { name: /Explore/ });
  await userEvent.setup().click(screen.getByRole('button', { name: 'Learn' }));
  await screen.findByRole('heading', { name: 'Learn Chemistry' });
  return { backend };
}

async function openFirstLesson() {
  const user = userEvent.setup();
  await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
  await screen.findByTestId('lesson-progress');
  return user;
}

describe('Learning Core (web)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('the catalog lists the seeded lessons', async () => {
    await setupApp();
    await screen.findByTestId('lesson-list');
    expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
    expect(screen.getByText('Valence Electrons')).toBeInTheDocument();
    expect(screen.getByText('Chemical Formulas')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Start lesson' }).length).toBe(3);
  });

  test('opening a lesson renders sections, live spotlight element, and questions', async () => {
    const { backend } = await setupApp();
    await openFirstLesson();
    expect(screen.getByText('Why arrangements matter')).toBeInTheDocument();
    // The chemistry_spotlight section fetched live engine data for oxygen.
    await screen.findByTestId('spotlight-O');
    expect(screen.getByTestId('element-config')).toHaveTextContent('1s');
    expect(screen.getByTestId('element-valence')).toHaveTextContent('6');
    expect(screen.getByTestId('question-ec-1')).toBeInTheDocument();
    expect(screen.getByTestId('question-ec-2')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        backend.requests.some((r) => r.url.endsWith('/elements/O')),
      ).toBe(true);
    });
  });

  test('marking a section complete updates the progress bar from the server', async () => {
    await setupApp(async (method, url, body) => {
      if (method === 'POST' && url.includes('/sections/intro/complete')) {
        return jsonResponse(200, {
          ...freshProgress,
          completed_sections: ['intro'],
          progress_percent: 33,
        });
      }
      return defaultHandler(method, url, body);
    });
    const user = await openFirstLesson();
    expect(screen.getByTestId('lesson-progress')).toHaveAttribute('aria-valuenow', '0');
    await user.click(screen.getByTestId('complete-intro'));
    await waitFor(() => {
      expect(screen.getByTestId('lesson-progress')).toHaveAttribute('aria-valuenow', '33');
    });
    expect(screen.getByTestId('lesson-progress-label')).toHaveTextContent('33% complete');
  });

  test('a correct answer shows the verdict and explanation', async () => {
    await setupApp();
    const user = await openFirstLesson();
    await user.type(
      screen.getByLabelText('How many electrons can a single 2p subshell hold at most?'),
      '6',
    );
    await user.click(screen.getByTestId('submit-ec-1'));
    await screen.findByTestId('feedback-ec-1');
    expect(screen.getByTestId('feedback-ec-1')).toHaveTextContent('Correct!');
    expect(screen.getByTestId('feedback-ec-1')).toHaveTextContent('orbital diagram');
  });

  test('an incorrect answer shows retry feedback, not the answer key', async () => {
    await setupApp();
    const user = await openFirstLesson();
    await user.click(screen.getByRole('radio', { name: 'Aufbau principle' }));
    await user.click(screen.getByTestId('submit-ec-2'));
    await screen.findByTestId('feedback-ec-2');
    expect(screen.getByTestId('feedback-ec-2')).toHaveTextContent('Not quite');
    expect(screen.getByTestId('feedback-ec-2')).not.toHaveTextContent('Correct!');
  });

  test('an answer that fails validation surfaces a user-facing message', async () => {
    await setupApp(async (method, url, body) => {
      if (method === 'POST' && url.includes('/answers')) {
        return jsonResponse(422, {
          detail: {
            code: 'invalid_answer',
            message: 'Answers must be 300 characters or fewer.',
          },
        });
      }
      return defaultHandler(method, url, body);
    });
    const user = await openFirstLesson();
    await user.type(
      screen.getByLabelText('How many electrons can a single 2p subshell hold at most?'),
      'way too many electrons to be a valid answer for this question',
    );
    await user.click(screen.getByTestId('submit-ec-1'));
    await screen.findByTestId('question-error-ec-1');
    expect(screen.getByRole('alert')).toHaveTextContent('300 characters');
  });

  test('a network failure loading the catalog shows a network error', async () => {
    await setupApp(async (_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/lessons')) throw new TypeError('Failed to fetch');
      return jsonResponse(404, { detail: 'not found' });
    });
    await screen.findByTestId('catalog-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the Chemora server/);
  });

  test('a server failure loading the catalog hides internals', async () => {
    await setupApp(async (_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/lessons')) return jsonResponse(500, { detail: 'boom' });
      return jsonResponse(404, { detail: 'not found' });
    });
    await screen.findByTestId('catalog-error');
    expect(screen.queryByText(/boom/)).toBeNull();
  });

  test('an unknown lesson shows a user-facing error with a way back', async () => {
    await setupApp(async (method, url, body) => {
      if (url.includes('/learning/lessons/electron-configuration')) {
        return jsonResponse(404, {
          detail: { code: 'lesson_not_found', message: 'Lesson not found.' },
        });
      }
      return defaultHandler(method, url, body);
    });
    await userEvent.setup().click(screen.getAllByRole('button', { name: 'Start lesson' })[0]);
    await screen.findByTestId('lesson-error');
    expect(screen.getByRole('alert')).toHaveTextContent('Lesson not found.');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Back to lessons' }));
    await screen.findByTestId('lesson-list');
  });

  test('returning to the catalog after viewing a lesson works', async () => {
    await setupApp();
    const user = await openFirstLesson();
    await user.click(screen.getByRole('button', { name: /All lessons/ }));
    await screen.findByTestId('lesson-list');
    expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
  });

  // -- M25: richer practice and molecule spotlights -------------------------

  async function openLessonAt(index: number) {
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Start lesson' })[index]);
    return user;
  }

  test('a molecule spotlight renders live engine analysis from the chemistry API', async () => {
    const { backend } = await setupApp();
    await openLessonAt(2);
    await screen.findByTestId('molecule-spotlight-H2O');
    // The values shown come from the engine response, not lesson content.
    expect(screen.getByTestId('identity-formula')).toHaveTextContent('H2O');
    expect(screen.getByTestId('identity-average-mass')).toHaveTextContent('18.015');
    await waitFor(() => {
      expect(backend.requests.some((r) => r.url.endsWith('/chemistry/explore'))).toBe(
        true,
      );
    });
  });

  test('a formula question accepts equivalent notation graded by the server', async () => {
    await setupApp();
    const user = await openLessonAt(2);
    const input = await screen.findByLabelText(
      'Which chemical formula represents a molecule with two hydrogen atoms and one oxygen atom?',
    );
    await user.type(input, 'HOH');
    await user.click(screen.getByTestId('submit-fm-1'));
    await screen.findByTestId('feedback-fm-1');
    expect(screen.getByTestId('feedback-fm-1')).toHaveTextContent('Correct!');
  });

  test('no practice results are shown before an attempt', async () => {
    await setupApp();
    await openFirstLesson();
    await screen.findByTestId('question-ec-1');
    expect(screen.queryByTestId('practice-results')).toBeNull();
  });

  test('practice results summarize a correct attempt', async () => {
    await setupApp();
    const user = await openFirstLesson();
    await user.type(
      screen.getByLabelText('How many electrons can a single 2p subshell hold at most?'),
      '6',
    );
    await user.click(screen.getByTestId('submit-ec-1'));
    await screen.findByTestId('practice-results');
    expect(screen.getByTestId('results-attempted')).toHaveTextContent('1 of 2');
    expect(screen.getByTestId('results-correct')).toHaveTextContent('1');
    expect(screen.getByTestId('results-incorrect')).toHaveTextContent('0');
    // Accuracy is measured over attempts made, not the whole question set.
    expect(screen.getByTestId('results-accuracy')).toHaveTextContent('100%');
  });

  test('practice results flag an incorrect attempt for another look', async () => {
    await setupApp();
    const user = await openFirstLesson();
    await user.click(screen.getByRole('radio', { name: 'Aufbau principle' }));
    await user.click(screen.getByTestId('submit-ec-2'));
    await screen.findByTestId('practice-results');
    expect(screen.getByTestId('results-incorrect')).toHaveTextContent('1');
    expect(screen.getByTestId('results-accuracy')).toHaveTextContent('0%');
    // The answer key is never revealed, only the explanation.
    expect(screen.getByTestId('practice-results')).not.toHaveTextContent("Hund's rule");
  });
});
