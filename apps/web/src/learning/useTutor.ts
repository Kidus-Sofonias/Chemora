import { useCallback, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type { TutorTurn } from '../api/types';

/**
 * AI Chemistry Tutor conversation state (M29).
 *
 * The tutor endpoint composes every answer server-side (lesson context +
 * ChemEngine tools + AI provider). The client only renders turns and forwards
 * prior user/assistant text as conversation history; it never talks to an AI
 * provider and never computes chemistry.
 *
 * Error contract: structured backend errors (`detail.code` + `detail.message`)
 * carry a user-facing message; network failures and unexpected server errors
 * are replaced by generic fallbacks so internals never reach the UI.
 */
export interface TutorMessage {
  role: 'user' | 'assistant';
  content: string;
}

export type TutorSendState =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'error'; message: string };

const NETWORK_MESSAGE =
  'Cannot reach the Chemora server. Check your connection and try again.';
const SERVER_MESSAGE =
  'The tutor is unavailable right now. Please try again in a moment.';

function tutorErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.isNetworkError) {
      return NETWORK_MESSAGE;
    }
    if (err.code !== null && err.message) {
      return err.message;
    }
  }
  return SERVER_MESSAGE;
}

export function useTutor(api: ApiClient, lessonSlug?: string) {
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [sendState, setSendState] = useState<TutorSendState>({ kind: 'idle' });

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || sendState.kind === 'sending') {
        return;
      }
      const history: TutorTurn[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setSendState({ kind: 'sending' });
      try {
        const result = await api.askTutor(text, history, lessonSlug);
        setMessages((prev) => [...prev, { role: 'assistant', content: result.answer }]);
        setSendState({ kind: 'idle' });
      } catch (err: unknown) {
        // The user's message stays in the transcript; the failure is shown as
        // a retryable status rather than removing anything.
        setSendState({ kind: 'error', message: tutorErrorMessage(err) });
      }
    },
    [api, lessonSlug, messages, sendState.kind],
  );

  const clear = useCallback(() => {
    if (sendState.kind !== 'sending') {
      setMessages([]);
      setSendState({ kind: 'idle' });
    }
  }, [sendState.kind]);

  return { messages, sendState, send, clear };
}
