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
  type Handler,
} from './helpers';

/**
 * M29 + M30 AI Chemistry Tutor — web tests.
 *
 * The real ApiClient/AuthService run against the scriptable fake backend.
 * Coverage: the auth gate, the empty state, the streaming round-trip through
 * persistent conversations, server-side history loading, streaming failure
 * (SSE error frames + non-2xx), retry states, conversation switching and
 * deletion, and metadata hygiene (tool payloads/provider details never
 * rendered).
 */

const CONVERSATION_ID = '11111111-1111-1111-1111-111111111111';

/** Build a Response whose body is an SSE stream of the given JSON events. */
function sseResponse(events: object[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(event)}\n\n`),
        );
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

/** A deferred SSE response: frames are released when the test resolves it. */
function deferredStream(): {
  response: Response;
  push: (event: object) => void;
  close: () => void;
} {
  const encoder = new TextEncoder();
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return {
    response: new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }),
    push(event) {
      controller!.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
    },
    close() {
      controller!.close();
    },
  };
}

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
  await screen.findByRole('button', { name: /Explore/ });
  return backend;
}

async function openTutor() {
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /Tutor/ }));
  return user;
}

interface StreamedRequest {
  body: { message: string };
  url: string;
}

function tutorStreamHandler(
  streamed: StreamedRequest[],
  events: object[] | ((request: { message: string }) => object[]),
): Handler {
  return (_method, url, body) => {
    if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
    if (url.endsWith('/learning/tutor/conversations') && _method === 'POST') {
      return jsonResponse(201, {
        id: CONVERSATION_ID,
        title: '',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        message_count: 0,
      });
    }
    if (url.endsWith('/learning/tutor/conversations')) {
      return jsonResponse(200, { conversations: [] });
    }
    if (url.endsWith('/messages')) {
      const payload = body as { message: string };
      streamed.push({ url, body: payload });
      const frames =
        typeof events === 'function' ? events(payload) : events;
      return sseResponse(frames);
    }
    return jsonResponse(404, { detail: 'not found' });
  };
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

  test('creates a conversation and streams the answer incrementally', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    const streamed: StreamedRequest[] = [];
    backend.setHandler(
      tutorStreamHandler(streamed, [
        { type: 'delta', text: 'Water is ' },
        { type: 'delta', text: 'H2O — about 18.02 g/mol.' },
        { type: 'done', tools_used: ['compute_property'], lesson_slugs: ['molar-mass'] },
      ]),
    );

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'What is the molar mass of water?');
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-message-assistant');
    expect(screen.getByTestId('tutor-message-user')).toBeInTheDocument();
    expect(screen.getByTestId('tutor-message-assistant')).toHaveTextContent('18.02 g/mol');
    expect(screen.queryByTestId('tutor-empty')).toBeNull();

    // The client creates the conversation and streams the message into it;
    // it does NOT send client-side history — history lives server-side.
    const created = backend.requests.filter((r) =>
      r.url.endsWith('/learning/tutor/conversations'),
    );
    expect(created.length).toBe(1);
    expect(streamed.length).toBe(1);
    expect(streamed[0].body).toEqual({ message: 'What is the molar mass of water?' });
    expect(streamed[0].url).toContain(`/learning/tutor/conversations/${CONVERSATION_ID}/messages`);
    expect(streamed[0].body).not.toHaveProperty('history');
  });

  test('renders a partial answer before the stream completes', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    const deferred = deferredStream();
    backend.setHandler((method, url, body) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor/conversations') && method === 'POST') {
        return jsonResponse(201, {
          id: CONVERSATION_ID,
          title: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          message_count: 0,
        });
      }
      if (url.endsWith('/messages')) {
        void body;
        return deferred.response;
      }
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-user');

    deferred.push({ type: 'delta', text: 'Partial answer so far' });
    await waitFor(() => {
      expect(screen.getByTestId('tutor-message-assistant')).toHaveTextContent(
        'Partial answer so far',
      );
    });
    // Still streaming — the done marker has not arrived.
    expect(screen.getByTestId('tutor-streaming')).toBeInTheDocument();

    deferred.push({ type: 'done', tools_used: [], lesson_slugs: [] });
    deferred.close();
    await waitFor(() => {
      expect(screen.queryByTestId('tutor-streaming')).toBeNull();
    });
  });

  test('loads persisted history from the server when switching conversations', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler((method, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor/conversations') && method === 'POST') {
        return jsonResponse(201, {
          id: CONVERSATION_ID,
          title: 'Stored chat',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          message_count: 2,
        });
      }
      if (url.endsWith('/learning/tutor/conversations')) {
        return jsonResponse(200, {
          conversations: [
            {
              id: CONVERSATION_ID,
              title: 'Stored chat',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              message_count: 2,
            },
          ],
        });
      }
      if (url.includes(`/learning/tutor/conversations/${CONVERSATION_ID}`)) {
        return jsonResponse(200, {
          id: CONVERSATION_ID,
          title: 'Stored chat',
          messages: [
            { role: 'user', content: 'Earlier question' },
            { role: 'assistant', content: 'Earlier answer' },
          ],
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.click(screen.getByTestId('tutor-toggle-conversations'));
    await user.click(screen.getByTestId(`tutor-open-${CONVERSATION_ID}`));

    await screen.findByText('Earlier question');
    expect(screen.getByText('Earlier answer')).toBeInTheDocument();
    // The transcript shows server-side history; the client never supplied it.
    expect(screen.getByTestId('tutor-message-user')).toBeInTheDocument();
    expect(screen.getByTestId('tutor-message-assistant')).toBeInTheDocument();
  });

  test('shows a loading state while waiting for the first stream byte', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    const deferred = deferredStream();
    backend.setHandler((method, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor/conversations') && method === 'POST') {
        return jsonResponse(201, {
          id: CONVERSATION_ID,
          title: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          message_count: 0,
        });
      }
      if (url.endsWith('/messages')) return deferred.response;
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));

    // The stream response resolves quickly; the visible in-flight state is
    // "streaming" with the composer disabled until the answer finishes.
    await screen.findByTestId('tutor-message-user');
    await screen.findByTestId('tutor-streaming');
    expect(screen.getByTestId('tutor-input')).toBeDisabled();

    deferred.push({ type: 'delta', text: 'Done.' });
    deferred.push({ type: 'done', tools_used: [], lesson_slugs: [] });
    deferred.close();
    await screen.findByText('Done.');
    await waitFor(() => {
      expect(screen.queryByTestId('tutor-streaming')).toBeNull();
    });
  });

  test('surfaces structured backend errors before streaming starts', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler((method, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor/conversations') && method === 'POST') {
        return jsonResponse(201, {
          id: CONVERSATION_ID,
          title: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          message_count: 0,
        });
      }
      if (url.endsWith('/messages')) {
        return jsonResponse(429, {
          detail: { code: 'rate_limited', message: "You're sending questions too quickly." },
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/too quickly/);
    expect(screen.getByTestId('tutor-message-user')).toBeInTheDocument();
  });

  test('surfaces mid-stream SSE error frames', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler(
      tutorStreamHandler([], [
        { type: 'delta', text: 'Partial…' },
        { type: 'error', code: 'ai_timeout', message: 'The tutoring service took too long.' },
      ]),
    );

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/took too long/);
  });

  test('distinguishes a network failure from a server error', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hello');
    backend.failNextRequestOnce();
    await user.click(screen.getByTestId('tutor-send'));

    await screen.findByTestId('tutor-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the Chemora server/);
  });

  test('never exposes tool payloads or provider metadata in the transcript', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler(
      tutorStreamHandler([], [
        { type: 'delta', text: 'The molar mass of water is 18.02 g/mol.' },
        { type: 'done', tools_used: ['compute_property'], lesson_slugs: ['molar-mass'] },
      ]),
    );

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'mass of water?');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-assistant');

    expect(screen.queryByText(/tools_used/)).toBeNull();
    expect(screen.queryByText(/lesson_slugs/)).toBeNull();
    expect(screen.queryByText(/compute_property/)).toBeNull();
  });

  test('deletes the open conversation and resets to the empty state', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    let deleted = false;
    backend.setHandler((method, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/learning/tutor/conversations') && method === 'POST') {
        return jsonResponse(201, {
          id: CONVERSATION_ID,
          title: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          message_count: 0,
        });
      }
      if (url.endsWith('/messages')) {
        return sseResponse([
          { type: 'delta', text: 'Answer.' },
          { type: 'done', tools_used: [], lesson_slugs: [] },
        ]);
      }
      if (
        url.endsWith(`/learning/tutor/conversations/${CONVERSATION_ID}`) &&
        method === 'DELETE'
      ) {
        deleted = true;
        return jsonResponse(200, { deleted: true });
      }
      return jsonResponse(404, { detail: 'not found' });
    });

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hi');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-assistant');

    await user.click(screen.getByTestId('tutor-delete-conversation'));
    await waitFor(() => {
      expect(deleted).toBe(true);
    });
    await screen.findByTestId('tutor-empty');
    expect(screen.queryByTestId('tutor-message-user')).toBeNull();
  });

  test('new conversation button clears the local view', async () => {
    const backend = await setupApp();
    const user = await openTutor();
    backend.setHandler(
      tutorStreamHandler([], [
        { type: 'delta', text: 'Answer.' },
        { type: 'done', tools_used: [], lesson_slugs: [] },
      ]),
    );

    await user.type(screen.getByLabelText(/Ask your chemistry question/i), 'hi');
    await user.click(screen.getByTestId('tutor-send'));
    await screen.findByTestId('tutor-message-assistant');

    await user.click(screen.getByTestId('tutor-new-conversation'));
    await screen.findByTestId('tutor-empty');
    expect(screen.queryByTestId('tutor-message-assistant')).toBeNull();
  });
});
