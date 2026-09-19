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
  type FakeBackend,
} from './helpers';

/**
 * M29 AI Chemistry Tutor — web tests.
 *
 * The real ApiClient + AuthService run against the scriptable fake backend,
 * exactly like the explorer/learning suites. Assertions cover the M29
 * acceptance surface: auth gating, conversation round-trip, distinct
 * loading/empty/error states, structured-error surfacing, and the fact that
 * the client never sends or receives provider/tool internals.
 */

async function setupApp(): Promise<FakeBackend> {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler((_m, url) => {
    if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
    return jsonResponse(404, { detail: 'not found' });
  });
  render(<App service={service} provider={provider} api={api} />);
  // Wait for the authenticated shell with the section nav.
  await screen.findByRole('button', { name: /Explore/ });
  return backend;
}

async function openTutor() {
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /Tutor/ }));
  return user;
}

describe('AI Chemistry Tutor (web)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('tutor entry point is gated behind authentication', async () => {
    const backend = installFakeBackend();
    const provider = new FakeGoogleProvider();
    const api = new ApiClient('http://test');
    const service = new ApiAuthService(api);
    backend.setHandler(() => jsonResponse(401, { detail: 'Not authenticated' }));
    render(<App service={service} provider={provider} api={api} />);

    // The login screen is shown instead of any tutor content.
    await screen.findByTestId('google-sign-in-host');
    expect(screen.queryByRole('button', { name: /Tutor/ })).toBeNull();
  });

  test('renders the empty state before the first question', async () => {
    await setupApp();
    await openTutor();

    expect(screen.getByTestId('tutor-empty')).toBeInTheDocument();
    expect(screen.getByTestId('tutor-transcript')).toBeInTheDocument();
    expect(screen.getByLabelText(/Ask your chemistry question/i)).toBeInTheDocument();
  });

  test('sends a question and renders the tutor answer', async () => {
    const backend = await setupApp();
    backend.setHandler((method, url, body) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) {
        expect(method).toBe('POST');
        const payload = body as { message: string; history: unknown[] };
        expect(payload.message).toBe('What is the molar mass of water?');
        expect(payload.history).toEqual([]);
        return jsonResponse(200, {
          answer: 'Water is H2O — about 18.02 g/mol.',
          lesson_slugs: ['molar-mass'],
          tools_used: ['compute_property'],
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'What is the molar mass of water?');
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-message-assistant');
    expect(screen.getByTestId('tutor-message-user')).toBeInTheDocument();
    expect(screen.getByTestId('tutor-message-assistant')).toHaveTextContent('18.02 g/mol');
    expect(screen.queryByTestId('tutor-empty')).toBeNull();
  });

  test('sends prior turns as conversation history', async () => {
    const backend = await setupApp();
    const tutorBodies: unknown[] = [];
    let call = 0;
    backend.setHandler((_m, url, body) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) {
        tutorBodies.push(body);
        call += 1;
        return jsonResponse(200, {
          answer: call === 1 ? 'H2O is water.' : 'Its molar mass is about 18.02 g/mol.',
          lesson_slugs: [],
          tools_used: [],
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'What is H2O?');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByText('H2O is water.');

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'And its mass?');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByText('Its molar mass is about 18.02 g/mol.');

    expect(tutorBodies.length).toBe(2);
    const second = tutorBodies[1] as { history: { role: string; content: string }[] };
    expect(second.history).toEqual([
      { role: 'user', content: 'What is H2O?' },
      { role: 'assistant', content: 'H2O is water.' },
    ]);
  });

  test('shows a loading state while waiting for the answer', async () => {
    const backend = await setupApp();
    let resolveTutor: (v: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveTutor = resolve;
    });
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) return pending;
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));

    expect(await screen.findByTestId('tutor-loading')).toBeInTheDocument();
    // Input is disabled while a request is in flight.
    expect(screen.getByTestId('tutor-input')).toBeDisabled();

    resolveTutor!(
      jsonResponse(200, { answer: 'Done.', lesson_slugs: [], tools_used: [] }),
    );
    await screen.findByText('Done.');
    expect(screen.queryByTestId('tutor-loading')).toBeNull();
  });

  test('surfaces structured backend errors and keeps the transcript', async () => {
    const backend = await setupApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) {
        return jsonResponse(429, {
          detail: { code: 'rate_limited', message: "You're sending questions too quickly." },
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/too quickly/);
    // The failed question stays in the transcript for retry context.
    expect(screen.getByTestId('tutor-message-user')).toBeInTheDocument();
  });

  test('distinguishes a network failure from a server error', async () => {
    const backend = await setupApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    backend.failNextRequestOnce();
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the Chemora server/);
  });

  test('never exposes tool payloads or provider metadata in the transcript', async () => {
    const backend = await setupApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) {
        return jsonResponse(200, {
          answer: 'The molar mass of water is 18.02 g/mol.',
          lesson_slugs: ['molar-mass'],
          tools_used: ['compute_property'],
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'mass of water?');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-assistant');

    // Raw metadata keys must not be rendered anywhere in the UI.
    expect(screen.queryByText(/tools_used/)).toBeNull();
    expect(screen.queryByText(/lesson_slugs/)).toBeNull();
    expect(screen.queryByText(/compute_property/)).toBeNull();
  });

  test('clear resets the conversation to the empty state', async () => {
    const backend = await setupApp();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor')) {
        return jsonResponse(200, { answer: 'Answer.', lesson_slugs: [], tools_used: [] });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = await openTutor();

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hi');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-assistant');

    await user.click(screen.getByTestId('tutor-clear'));
    await waitFor(() => {
      expect(screen.getByTestId('tutor-empty')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('tutor-message-user')).toBeNull();
  });
});
