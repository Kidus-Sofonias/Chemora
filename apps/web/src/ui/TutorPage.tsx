import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useApiClient } from '../api/apiContext';
import { useTutor } from '../learning/useTutor';
import './learning.css';

/**
 * The AI Chemistry Tutor page (M29 + M30).
 *
 * A signed-in student chats with the server-side tutor inside persistent,
 * server-owned conversations. Questions are streamed back as Server-Sent
 * Events and rendered incrementally. The client never talks to an AI
 * provider, never sees tool payloads, and never computes chemistry itself —
 * conversation history lives on the server and ownership is enforced there.
 */
export function TutorPage({ lessonSlug }: { lessonSlug?: string }) {
  const api = useApiClient();
  const {
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
  } = useTutor(api, lessonSlug);
  const [draft, setDraft] = useState('');
  const [listOpen, setListOpen] = useState(false);
  const sending = sendState.kind === 'sending' || sendState.kind === 'streaming';

  // Load the persisted conversation list whenever the panel opens.
  useEffect(() => {
    if (listOpen) {
      void refreshConversations();
    }
  }, [listOpen, refreshConversations]);

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    transcriptRef.current?.scrollTo?.({
      top: transcriptRef.current.scrollHeight,
    });
  }, [messages.length, messages[messages.length - 1]?.content, sendState.kind]);

  const canSend = draft.trim().length > 0 && !sending;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }
    const question = draft;
    setDraft('');
    void send(question);
  };

  return (
    <section className="learning tutor" aria-labelledby="tutor-title">
      <div className="explorer-head">
        <h2 id="tutor-title">Chemistry Tutor</h2>
        <p className="muted">
          Ask questions about the chemistry you are learning. Deterministic
          values (masses, formulas, electron configurations) are computed by
          the Chemora chemistry engine — not invented by the tutor.
        </p>
        <div className="tutor-toolbar">
          <button
            type="button"
            className="button"
            onClick={() => void startConversation()}
            disabled={sending}
            data-testid="tutor-new-conversation"
          >
            New conversation
          </button>
          <button
            type="button"
            className="button"
            onClick={() => setListOpen((open) => !open)}
            aria-expanded={listOpen}
            data-testid="tutor-toggle-conversations"
          >
            {listOpen ? 'Hide conversations' : 'My conversations'}
          </button>
          {conversationId ? (
            <button
              type="button"
              className="button"
              onClick={() => void deleteConversation(conversationId)}
              disabled={sending}
              data-testid="tutor-delete-conversation"
            >
              Delete conversation
            </button>
          ) : null}
        </div>
        {lessonSlug ? (
          <p className="help muted" data-testid="tutor-lesson-context">
            Tutoring with context from your current lesson.
          </p>
        ) : null}
      </div>

      {listOpen ? (
        <div className="card tutor-conversations" data-testid="tutor-conversations">
          {conversations.length === 0 ? (
            <p className="help muted">No conversations yet.</p>
          ) : (
            <ul className="tutor-conversation-list">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <button
                    type="button"
                    className={`button${conversation.id === conversationId ? ' active' : ''}`}
                    onClick={() => void openConversation(conversation.id)}
                    data-testid={`tutor-open-${conversation.id}`}
                  >
                    {conversation.title || 'Conversation'} (
                    {conversation.message_count})
                  </button>
                  <button
                    type="button"
                    className="button"
                    onClick={() => void deleteConversation(conversation.id)}
                    aria-label={`Delete ${conversation.title || 'conversation'}`}
                    data-testid={`tutor-delete-${conversation.id}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      <div
        className="card tutor-transcript"
        data-testid="tutor-transcript"
        ref={transcriptRef}
      >
        {messages.length === 0 && !loadingHistory ? (
          <div className="tutor-empty" data-testid="tutor-empty">
            <h3>Hi! I'm your chemistry tutor.</h3>
            <p>
              Try asking something like “What is the molar mass of water?” or
              “Why does chromium break the aufbau pattern?”
            </p>
          </div>
        ) : null}
        {loadingHistory ? (
          <p className="status" role="status" data-testid="tutor-history-loading">
            Loading conversation…
          </p>
        ) : null}
        <ol className="tutor-messages" aria-label="Tutor conversation">
          {messages.map((message, index) => (
            <li
              key={index}
              className={`tutor-message tutor-${message.role}`}
              data-testid={`tutor-message-${message.role}`}
            >
              <span className="tutor-role">
                {message.role === 'user' ? 'You' : 'Tutor'}
              </span>
              <p>{message.content}</p>
            </li>
          ))}
        </ol>
        {sendState.kind === 'sending' ? (
          <p className="status" role="status" data-testid="tutor-loading">
            Thinking…
          </p>
        ) : null}
        {sendState.kind === 'streaming' ? (
          <p className="status" role="status" data-testid="tutor-streaming">
            Tutor is typing…
          </p>
        ) : null}
        {sendState.kind === 'error' ? (
          <div className="card error-card" role="alert" data-testid="tutor-error">
            <p>{sendState.message}</p>
            <button type="button" className="button" onClick={clear}>
              Clear conversation
            </button>
          </div>
        ) : null}
      </div>

      <form className="tutor-form" onSubmit={submit} data-testid="tutor-form">
        <label className="help muted" htmlFor="tutor-input">
          Ask your chemistry question
        </label>
        <div className="tutor-input-row">
          <input
            id="tutor-input"
            className="explorer-input"
            type="text"
            value={draft}
            maxLength={1000}
            autoComplete="off"
            disabled={sending}
            onChange={(e) => setDraft(e.target.value)}
            data-testid="tutor-input"
          />
          <button
            type="submit"
            className="button"
            disabled={!canSend}
            data-testid="tutor-send"
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
          {messages.length > 0 && !sending ? (
            <button
              type="button"
              className="button"
              onClick={clear}
              data-testid="tutor-clear"
            >
              Clear
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
