import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useApiClient } from '../api/apiContext';
import { useTutor } from '../learning/useTutor';
import './learning.css';

/**
 * The AI Chemistry Tutor page (M29).
 *
 * A signed-in student chats with the server-side tutor: questions go to
 * POST /api/v1/learning/tutor with the existing Chemora session cookie, and
 * answers are composed on the backend from published lesson context, an
 * allowlisted ChemEngine tool loop, and the configured AI provider. The client
 * only renders the conversation — it never contacts a provider, never sees
 * tool payloads, and never computes chemistry itself.
 *
 * When opened from a lesson (`lessonSlug`), every request carries that slug so
 * the backend can prioritize the current lesson's published content.
 */
export function TutorPage({ lessonSlug }: { lessonSlug?: string }) {
  const api = useApiClient();
  const { messages, sendState, send, clear } = useTutor(api, lessonSlug);
  const [draft, setDraft] = useState('');
  const sending = sendState.kind === 'sending';

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    transcriptRef.current?.scrollTo?.({ top: transcriptRef.current.scrollHeight });
  }, [messages.length, sendState.kind]);

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
        {lessonSlug ? (
          <p className="help muted" data-testid="tutor-lesson-context">
            Tutoring with context from your current lesson.
          </p>
        ) : null}
      </div>

      <div className="card tutor-transcript" data-testid="tutor-transcript" ref={transcriptRef}>
        {messages.length === 0 ? (
          <div className="tutor-empty" data-testid="tutor-empty">
            <h3>Hi! I'm your chemistry tutor.</h3>
            <p>
              Try asking something like “What is the molar mass of water?” or
              “Why does chromium break the aufbau pattern?”
            </p>
          </div>
        ) : (
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
        )}
        {sending ? (
          <p className="status" role="status" data-testid="tutor-loading">
            Thinking…
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
