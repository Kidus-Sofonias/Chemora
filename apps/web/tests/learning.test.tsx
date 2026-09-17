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

/**
 * Learning Core (M24) integration tests.
 *
 * The REAL ApiClient/AuthService/pages run against a scripted fake backend —
 * no live server and no real Google account. Shapes mirror the backend
 * Pydantic contracts exactly.
 */

const catalog = {
  lessons: [
    {
      id: 'lesson-electron-configuration',
      slug: 'electron-configuration',
      title: 'Electron Configurations',
      description: 'How electrons arrange themselves around a nucleus.',
      subject: 'atomic structure',
      difficulty: 'beginner',
      estimated_minutes: 8,
      section_count: 5,
      question_count: 2,
    },
    {
      id: 'lesson-valence-electrons',
      slug: 'valence-electrons',
      title: 'Valence Electrons',
      description: 'The outermost electrons do the chemistry.',
      subject: 'atomic structure',
      difficulty: 'beginner',
      estimated_minutes: 6,
      section_count: 4,
      question_count: 1,
    },
  ],
};

const oxygenDetail = {
  atomic_number: 8,
  symbol: 'O',
  name: 'Oxygen',
  atomic_mass: 15.999,
  period: 2,
  group: 16,
  block: 'p',
  category: 'nonmetal',
  config_full: '1s2 2s2 2p4',
  config_shorthand: '[He] 2s2 2p4',
  noble_gas: 'He',
  valence_electrons: 6,
  core_electrons: 2,
  unpaired_electrons: 2,
  shells: { '1': 2, '2': 6 },
  subshells: { '1s': 2, '2s': 2, '2p': 4 },
  orbitals: [
    { orbital: '1s', electrons: 2, capacity: 2, subshell: 's', shell: 1 },
    { orbital: '2s', electrons: 2, capacity: 2, subshell: 's', shell: 2 },
    { orbital: '2p', electrons: 4, capacity: 6, subshell: 'p', shell: 2 },
  ],
  explanation: 'Electron Configuration of Oxygen (O, Z=8)',
};

const lessonDetail = {
  id: 'lesson-electron-configuration',
  slug: 'electron-configuration',
  title: 'Electron Configurations',
  description: 'How electrons arrange themselves around a nucleus.',
  subject: 'atomic structure',
  difficulty: 'beginner',
  estimated_minutes: 8,
  sections: [
    {
      id: 'intro',
      kind: 'introduction',
      title: 'Why arrangements matter',
      body: ['Every atom contains electrons.'],
      element_symbol: null,
      questions: [],
    },
    {
      id: 'spotlight',
      kind: 'chemistry_spotlight',
      title: 'See it live',
      body: ['Pick an element below.'],
      element_symbol: 'O',
      questions: [],
    },
    {
      id: 'practice',
      kind: 'practice',
      title: 'Check your understanding',
      body: [],
      element_symbol: null,
      questions: [
        {
          id: 'ec-1',
          kind: 'number',
          prompt: 'How many electrons can a single 2p subshell hold at most?',
          options: [],
        },
        {
          id: 'ec-2',
          kind: 'multiple_choice',
          prompt: 'Which rule says degenerate orbitals fill singly before pairing?',
          options: ['Aufbau principle', "Hund's rule", 'Pauli exclusion principle'],
        },
      ],
    },
  ],
};

const freshProgress = {
  lesson_slug: 'electron-configuration',
  completed_sections: [],
  answers: {},
  progress_percent: 0,
  completed: false,
};

async function defaultHandler(
  _method: string,
  url: string,
  body: unknown,
): Promise<Response> {
  if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
  if (url.endsWith('/learning/lessons')) return jsonResponse(200, catalog);
  if (url.includes('/learning/lessons/electron-configuration/progress')) {
    return jsonResponse(200, freshProgress);
  }
  if (url.endsWith('/learning/lessons/electron-configuration')) {
    return jsonResponse(200, lessonDetail);
  }
  if (url.endsWith('/elements/O')) return jsonResponse(200, oxygenDetail);
  if (url.includes('/learning/lessons/electron-configuration/answers')) {
    const submission = body as { question_id: string; answer: string };
    const correct =
      submission.question_id === 'ec-1'
        ? submission.answer === '6'
        : submission.answer === "Hund's rule";
    return jsonResponse(200, {
      question_id: submission.question_id,
      correct,
      explanation: 'The engine says so — see the orbital diagram above.',
      progress: {
        ...freshProgress,
        answers: { [submission.question_id]: correct },
      },
    });
  }
  return jsonResponse(404, { detail: 'not found' });
}

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
    expect(screen.getAllByRole('button', { name: 'Start lesson' }).length).toBe(2);
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
});
