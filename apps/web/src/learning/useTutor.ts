import { useCallback, useRef, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type {
  TutorConversationMessage,
  TutorConversationSummary,
} from '../api/types';

/**
 * AI Chemistry Tutor conversation state (M29 + M30).
 *
 * Conversations are persisted server-side: history is loaded from the backend
 * (never supplied by the client), messages are streamed as Server-Sent Events
 * and rendered incrementally, and ownership is enforced by the session.
 *
 * Error contract: structured backend errors (`detail.code` + `detail.message`)
 * carry a user-facing message; network failures and unexpected server errors
 * are replaced by generic fallbacks so internals never reach the UI.
 */
export type TutorSendState =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'streaming' }
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
  const [messages, setMessages] = useState<TutorConversationMessage[]>([]);
  const [sendState, setSendState] = useState<TutorSendState>({ kind: 'idle' });
  const [conversations, setConversations] = useState<TutorConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const streamIndex = useRef(0);

  /** Create a conversation and switch to it (clearing the local view). */
  const startConversation = useCallback(async () => {
    const summary = await api.createTutorConversation();
    setMessages([]);
    setConversationId(summary.id);
    setSendState({ kind: 'idle' });
    setConversations((prev) => [summary, ...prev]);
    return summary.id;
  }, [api]);

  /** Load a conversation's persisted history from the server. */
  const openConversation = useCallback(
    async (id: string) => {
      setLoadingHistory(true);
      try {
        const detail = await api.getTutorConversation(id);
        setConversationId(detail.id);
        setMessages(
          detail.messages.map((m) => ({ role: m.role, content: m.content })),
        );
        setSendState({ kind: 'idle' });
      } catch (err: unknown) {
        setSendState({ kind: 'error', message: tutorErrorMessage(err) });
      } finally {
        setLoadingHistory(false);
      }
    },
    [api],
  );

  /** Refresh the conversation list (after create/delete elsewhere). */
  const refreshConversations = useCallback(async () => {
    try {
      const result = await api.listTutorConversations();
      setConversations(result.conversations);
    } catch {
      // The chat stays usable without the sidebar list.
    }
  }, [api]);

  /** Delete one conversation; if it was open, clear the view. */
  const deleteConversation = useCallback(
    async (id: string) => {
      await api.deleteTutorConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversationId === id) {
        setConversationId(null);
        setMessages([]);
        setSendState({ kind: 'idle' });
      }
    },
    [api, conversationId],
  );

  /**
   * Send a question into the current conversation and stream the answer.
   * Creates a conversation implicitly on first send when none is open.
   */
  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || sendState.kind === 'sending' || sendState.kind === 'streaming') {
        return;
      }
      let id = conversationId;
      try {
        if (!id) {
          const summary = await api.createTutorConversation();
          id = summary.id;
          setConversationId(id);
          setConversations((prev) => [summary, ...prev]);
        }
      } catch (err: unknown) {
        setSendState({ kind: 'error', message: tutorErrorMessage(err) });
        return;
      }

      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setSendState({ kind: 'sending' });
      let streamFailed: string | null = null;
      try {
        const response = await api.streamTutorMessage(id, text, lessonSlug);
        setSendState({ kind: 'streaming' });
        // Reserve the assistant turn; stream deltas into it incrementally.
        const slot = ++streamIndex.current;
        setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
        let streamed = '';
        for await (const event of api.tutorStreamEvents(response)) {
          if (event.type === 'delta') {
            streamed += event.text;
            const captured = slot;
            setMessages((prev) => {
              const next = [...prev];
              // The assistant message is the last element of this stream.
              for (let i = next.length - 1; i >= 0; i -= 1) {
                if (next[i].role === 'assistant') {
                  if (i === next.length - 1 || i === captured) {
                    next[i] = { ...next[i], content: streamed };
                  }
                  break;
                }
              }
              return next;
            });
          } else if (event.type === 'error') {
            // Mid-stream failure: the backend already surfaced a stable,
            // user-facing message — keep it verbatim.
            streamFailed = event.message;
            break;
          } else if (event.type === 'done') {
            break;
          }
        }
        // A stream that never delivered text leaves an empty assistant
        // bubble — replace it with the safe fallback.
        if (!streamed && !streamFailed) {
          setMessages((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i -= 1) {
              if (next[i].role === 'assistant') {
                next[i] = { ...next[i], content: SERVER_MESSAGE };
                break;
              }
            }
            return next;
          });
        }
        if (streamFailed) {
          setSendState({ kind: 'error', message: streamFailed });
          return;
        }
        setSendState({ kind: 'idle' });
      } catch (err: unknown) {
        // Remove the reserved empty assistant bubble on failure.
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i -= 1) {
            if (next[i].role === 'assistant' && next[i].content === '') {
              next.splice(i, 1);
              break;
            }
          }
          return next;
        });
        setSendState({ kind: 'error', message: tutorErrorMessage(err) });
      }
    },
    [api, conversationId, lessonSlug, sendState.kind],
  );

  /** Clear the local view without deleting server history. */
  const clear = useCallback(() => {
    if (sendState.kind !== 'sending' && sendState.kind !== 'streaming') {
      setMessages([]);
      setConversationId(null);
      setSendState({ kind: 'idle' });
    }
  }, [sendState.kind]);

  return {
    messages,
    sendState,
    send,
    clear,
    conversations,
    conversationId,
    loadingHistory,
    startConversation,
    openConversation,
    deleteConversation,
    refreshConversations,
  };
}
