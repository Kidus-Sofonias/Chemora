// Chemora Admin CMS — main application.
//
// Uses hash-based routing with React state (no router dependency needed).
// Pages: Dashboard, Lesson List, Lesson Editor, Preview.

import React, { useCallback, useEffect, useState } from 'react';
import type {
  AdminLesson,
  AdminLessonList,
  AdminLessonUpsert,
  AdminSectionUpsert,
  AdminQuestionUpsert,
  PreviewLesson,
} from './types';
import * as api from './api';
import './app.css';

type Page =
  | { kind: 'dashboard' }
  | { kind: 'list' }
  | { kind: 'edit'; slug: string | null }
  | { kind: 'preview'; slug: string };

function parseHash(): Page {
  const hash = window.location.hash.slice(1) || '/';
  if (hash === '/' || hash === '/dashboard') return { kind: 'dashboard' };
  if (hash === '/lessons') return { kind: 'list' };
  if (hash.startsWith('/lessons/new')) return { kind: 'edit', slug: null };
  if (hash.startsWith('/lessons/') && hash.endsWith('/preview')) {
    const slug = hash.split('/')[2];
    return { kind: 'preview', slug };
  }
  if (hash.startsWith('/lessons/')) {
    const slug = hash.split('/')[2];
    return { kind: 'edit', slug };
  }
  return { kind: 'dashboard' };
}

function navigate(hash: string) {
  window.location.hash = hash;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="sidebar-brand">Chemora Admin</div>
        <ul>
          <li>
            <a href="#/dashboard">Dashboard</a>
          </li>
          <li>
            <a href="#/lessons">Lessons</a>
          </li>
        </ul>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  );
}

function AuthGate() {
  return (
    <div className="auth-gate">
      <h1>Chemora Admin</h1>
      <p>You need to be signed in as an admin to access this page.</p>
      <a href="http://localhost:5173" className="btn btn-primary">
        Go to Chemora
      </a>
    </div>
  );
}

// --- Lesson payload helpers ---

function emptyLessonPayload(): AdminLessonUpsert {
  return {
    slug: '',
    title: '',
    description: '',
    subject: '',
    difficulty: 'beginner',
    estimated_minutes: 10,
    order: 1,
    sections: [],
  };
}

function lessonFromAdmin(lesson: AdminLesson): AdminLessonUpsert {
  return {
    slug: lesson.slug,
    title: lesson.title,
    description: lesson.description,
    subject: lesson.topic,
    difficulty: lesson.difficulty,
    estimated_minutes: lesson.estimated_minutes,
    order: lesson.ordering,
    sections: lesson.sections.map((s) => ({
      id: s.id,
      kind: s.kind,
      title: s.title,
      body: s.body,
      element_symbol: s.element_symbol,
      molecule_input: s.molecule_input,
      questions: s.questions.map((q) => ({
        id: q.id,
        kind: q.kind,
        prompt: q.prompt,
        correct: q.correct,
        explanation: q.explanation,
        options: q.options,
      })),
    })),
  };
}

// --- Components ---

function ErrorBanner({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="error-banner">{error}</div>;
}

function Dashboard({
  data,
  onNavigate,
}: {
  data: AdminLessonList | null;
  onNavigate: (h: string) => void;
}) {
  const lessons = data?.lessons ?? [];
  const published = lessons.filter((l) => l.published).length;
  const drafts = lessons.length - published;
  return (
    <div className="page">
      <h1>Dashboard</h1>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">{lessons.length}</div>
          <div className="stat-label">Total Lessons</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{published}</div>
          <div className="stat-label">Published</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{drafts}</div>
          <div className="stat-label">Drafts</div>
        </div>
      </div>
      <button className="btn btn-primary" onClick={() => onNavigate('/lessons')}>
        View All Lessons
      </button>
    </div>
  );
}

function LessonList({
  data,
  onNavigate,
  onPublish,
  onUnpublish,
}: {
  data: AdminLessonList | null;
  onNavigate: (h: string) => void;
  onPublish: (slug: string) => void;
  onUnpublish: (slug: string) => void;
}) {
  const lessons = data?.lessons ?? [];
  return (
    <div className="page">
      <div className="page-header">
        <h1>Lessons</h1>
        <button
          className="btn btn-primary"
          onClick={() => onNavigate('/lessons/new')}
        >
          + New Lesson
        </button>
      </div>
      <table className="lesson-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Difficulty</th>
            <th>Sections</th>
            <th>Questions</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {lessons.map((l) => (
            <tr key={l.slug}>
              <td>{l.title}</td>
              <td>
                <span
                  className={`badge ${l.published ? 'badge-published' : 'badge-draft'}`}
                >
                  {l.published ? 'Published' : 'Draft'}
                </span>
              </td>
              <td>{l.difficulty}</td>
              <td>{l.section_count}</td>
              <td>{l.question_count}</td>
              <td>
                {l.updated_at
                  ? new Date(l.updated_at).toLocaleDateString()
                  : '—'}
              </td>
              <td className="actions">
                <button
                  className="btn btn-small"
                  onClick={() => onNavigate(`/lessons/${l.slug}`)}
                >
                  Edit
                </button>
                <button
                  className="btn btn-small"
                  onClick={() => onNavigate(`/lessons/${l.slug}/preview`)}
                >
                  Preview
                </button>
                {l.published ? (
                  <button
                    className="btn btn-small btn-warning"
                    onClick={() => onUnpublish(l.slug)}
                  >
                    Unpublish
                  </button>
                ) : (
                  <button
                    className="btn btn-small btn-success"
                    onClick={() => onPublish(l.slug)}
                  >
                    Publish
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Lesson Editor ---

function SectionEditor({
  section,
  index,
  onChange,
  onRemove,
}: {
  section: AdminSectionUpsert;
  index: number;
  onChange: (updated: AdminSectionUpsert) => void;
  onRemove: () => void;
}) {
  const updateField = (field: string, value: unknown) => {
    onChange({ ...section, [field]: value } as AdminSectionUpsert);
  };
  const updateBody = (idx: number, value: string) => {
    const body = [...section.body];
    body[idx] = value;
    onChange({ ...section, body });
  };
  const addBody = () => onChange({ ...section, body: [...section.body, ''] });
  const removeBody = (idx: number) =>
    onChange({ ...section, body: section.body.filter((_, i) => i !== idx) });

  const updateQuestion = (
    qIdx: number,
    updated: AdminQuestionUpsert,
  ) => {
    const questions = [...section.questions];
    questions[qIdx] = updated;
    onChange({ ...section, questions });
  };
  const addQuestion = () => {
    const qId = `q-${Date.now()}`;
    onChange({
      ...section,
      questions: [
        ...section.questions,
        {
          id: qId,
          kind: 'multiple_choice',
          prompt: '',
          correct: '',
          explanation: '',
          options: ['', ''],
        },
      ],
    });
  };
  const removeQuestion = (qIdx: number) =>
    onChange({
      ...section,
      questions: section.questions.filter((_, i) => i !== qIdx),
    });

  return (
    <div className="section-editor">
      <div className="section-header">
        <span className="section-number">Section {index + 1}</span>
        <button className="btn btn-small btn-danger" onClick={onRemove}>
          Remove Section
        </button>
      </div>
      <div className="form-row">
        <label>
          Section ID
          <input
            value={section.id}
            onChange={(e) => updateField('id', e.target.value)}
            placeholder="e.g. intro"
          />
        </label>
        <label>
          Type
          <select
            value={section.kind}
            onChange={(e) => updateField('kind', e.target.value)}
          >
            <option value="introduction">Introduction</option>
            <option value="explanation">Explanation</option>
            <option value="chemistry_spotlight">Chemistry Spotlight</option>
            <option value="practice">Practice</option>
            <option value="summary">Summary</option>
          </select>
        </label>
        <label>
          Title
          <input
            value={section.title}
            onChange={(e) => updateField('title', e.target.value)}
          />
        </label>
      </div>
      {(section.kind === 'chemistry_spotlight') && (
        <div className="form-row">
          <label>
            Element Symbol
            <input
              value={section.element_symbol ?? ''}
              onChange={(e) =>
                updateField('element_symbol', e.target.value || null)
              }
              placeholder="e.g. O"
            />
          </label>
          <label>
            Molecule Input
            <input
              value={section.molecule_input ?? ''}
              onChange={(e) =>
                updateField('molecule_input', e.target.value || null)
              }
              placeholder="e.g. H2O"
            />
          </label>
        </div>
      )}
      {section.kind !== 'practice' && (
        <div className="body-editor">
          <label>Content (body paragraphs)</label>
          {section.body.map((para, idx) => (
            <div key={idx} className="body-para-row">
              <textarea
                value={para}
                onChange={(e) => updateBody(idx, e.target.value)}
                rows={2}
              />
              <button
                className="btn btn-small btn-danger"
                onClick={() => removeBody(idx)}
              >
                ×
              </button>
            </div>
          ))}
          <button className="btn btn-small" onClick={addBody}>
            + Add Paragraph
          </button>
        </div>
      )}
      {section.kind === 'practice' && (
        <div className="questions-editor">
          <label>Questions</label>
          {section.questions.map((q, qIdx) => (
            <QuestionEditor
              key={q.id}
              question={q}
              onChange={(updated) => updateQuestion(qIdx, updated)}
              onRemove={() => removeQuestion(qIdx)}
            />
          ))}
          <button className="btn btn-small" onClick={addQuestion}>
            + Add Question
          </button>
        </div>
      )}
    </div>
  );
}

function QuestionEditor({
  question,
  onChange,
  onRemove,
}: {
  question: AdminQuestionUpsert;
  onChange: (updated: AdminQuestionUpsert) => void;
  onRemove: () => void;
}) {
  const updateOption = (idx: number, value: string) => {
    const options = [...question.options];
    options[idx] = value;
    onChange({ ...question, options });
  };
  const addOption = () =>
    onChange({ ...question, options: [...question.options, ''] });
  const removeOption = (idx: number) =>
    onChange({
      ...question,
      options: question.options.filter((_, i) => i !== idx),
    });

  return (
    <div className="question-editor">
      <div className="question-header">
        <span>Question: {question.id}</span>
        <button className="btn btn-small btn-danger" onClick={onRemove}>
          Remove
        </button>
      </div>
      <div className="form-row">
        <label>
          ID
          <input
            value={question.id}
            onChange={(e) => onChange({ ...question, id: e.target.value })}
          />
        </label>
        <label>
          Type
          <select
            value={question.kind}
            onChange={(e) => onChange({ ...question, kind: e.target.value })}
          >
            <option value="multiple_choice">Multiple Choice</option>
            <option value="numeric">Numeric</option>
            <option value="formula">Formula</option>
            <option value="element">Element</option>
          </select>
        </label>
      </div>
      <label>
        Prompt
        <textarea
          value={question.prompt}
          onChange={(e) => onChange({ ...question, prompt: e.target.value })}
          rows={2}
        />
      </label>
      <label>
        Correct Answer
        <input
          value={question.correct}
          onChange={(e) => onChange({ ...question, correct: e.target.value })}
        />
      </label>
      <label>
        Explanation
        <textarea
          value={question.explanation}
          onChange={(e) =>
            onChange({ ...question, explanation: e.target.value })
          }
          rows={2}
        />
      </label>
      {question.kind === 'multiple_choice' && (
        <div className="options-editor">
          <label>Options</label>
          {question.options.map((opt, idx) => (
            <div key={idx} className="option-row">
              <input
                value={opt}
                onChange={(e) => updateOption(idx, e.target.value)}
              />
              <button
                className="btn btn-small btn-danger"
                onClick={() => removeOption(idx)}
              >
                ×
              </button>
            </div>
          ))}
          <button className="btn btn-small" onClick={addOption}>
            + Add Option
          </button>
        </div>
      )}
    </div>
  );
}

function LessonEditor({
  slug,
  onSave,
  onCancel,
}: {
  slug: string | null;
  onSave: () => void;
  onCancel: () => void;
}) {
  const [payload, setPayload] = useState<AdminLessonUpsert>(
    emptyLessonPayload,
  );
  const [loading, setLoading] = useState(slug !== null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    api
      .getLesson(slug)
      .then((lesson) => setPayload(lessonFromAdmin(lesson)))
      .catch(() => setError('Failed to load lesson'))
      .finally(() => setLoading(false));
  }, [slug]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (slug) {
        await api.updateLesson(slug, payload);
      } else {
        await api.createLesson(payload);
      }
      onSave();
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 422) {
        const detail = err.body as {
          errors?: Array<{ field: string; message: string }>;
        };
        const msgs = detail.errors?.map((e) => e.message).join('; ') || 'Validation failed';
        setError(msgs);
      } else {
        setError('Failed to save lesson');
      }
    } finally {
      setSaving(false);
    }
  };

  const addSection = () => {
    const id = `section-${Date.now()}`;
    setPayload({
      ...payload,
      sections: [
        ...payload.sections,
        {
          id,
          kind: 'introduction',
          title: '',
          body: [''],
          element_symbol: null,
          molecule_input: null,
          questions: [],
        },
      ],
    });
  };
  const updateSection = (idx: number, updated: AdminSectionUpsert) => {
    const sections = [...payload.sections];
    sections[idx] = updated;
    setPayload({ ...payload, sections });
  };
  const removeSection = (idx: number) =>
    setPayload({
      ...payload,
      sections: payload.sections.filter((_, i) => i !== idx),
    });

  if (loading) return <div className="page">Loading...</div>;

  const isNew = !slug;
  return (
    <div className="page">
      <div className="page-header">
        <h1>{isNew ? 'New Lesson' : 'Edit Lesson'}</h1>
        <div className="header-actions">
          <button className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
      <ErrorBanner error={error} />
      <div className="editor-form">
        <div className="form-row">
          <label>
            Slug
            <input
              value={payload.slug}
              onChange={(e) =>
                setPayload({ ...payload, slug: e.target.value })
              }
              placeholder="e.g. chemical-formulas"
              disabled={!isNew}
            />
          </label>
          <label>
            Title
            <input
              value={payload.title}
              onChange={(e) =>
                setPayload({ ...payload, title: e.target.value })
              }
            />
          </label>
        </div>
        <label>
          Description
          <textarea
            value={payload.description}
            onChange={(e) =>
              setPayload({ ...payload, description: e.target.value })
            }
            rows={3}
          />
        </label>
        <div className="form-row">
          <label>
            Subject
            <input
              value={payload.subject}
              onChange={(e) =>
                setPayload({ ...payload, subject: e.target.value })
              }
            />
          </label>
          <label>
            Difficulty
            <select
              value={payload.difficulty}
              onChange={(e) =>
                setPayload({ ...payload, difficulty: e.target.value })
              }
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
          <label>
            Est. Minutes
            <input
              type="number"
              value={payload.estimated_minutes}
              onChange={(e) =>
                setPayload({
                  ...payload,
                  estimated_minutes: parseInt(e.target.value) || 1,
                })
              }
              min={1}
            />
          </label>
          <label>
            Order
            <input
              type="number"
              value={payload.order}
              onChange={(e) =>
                setPayload({ ...payload, order: parseInt(e.target.value) || 1 })
              }
              min={1}
            />
          </label>
        </div>
        <div className="sections-editor">
          <h2>Sections</h2>
          {payload.sections.map((s, idx) => (
            <SectionEditor
              key={s.id}
              section={s}
              index={idx}
              onChange={(updated) => updateSection(idx, updated)}
              onRemove={() => removeSection(idx)}
            />
          ))}
          <button className="btn" onClick={addSection}>
            + Add Section
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Preview ---

function PreviewPage({ slug, onNavigate }: { slug: string; onNavigate: (h: string) => void }) {
  const [lesson, setLesson] = useState<PreviewLesson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .previewLesson(slug)
      .then(setLesson)
      .catch(() => setError('Failed to load preview'))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) return <div className="page">Loading preview...</div>;
  if (error || !lesson)
    return (
      <div className="page">
        <ErrorBanner error={error} />
      </div>
    );

  return (
    <div className="page preview-page">
      <div className="page-header">
        <h1>Preview: {lesson.title}</h1>
        <button
          className="btn"
          onClick={() => onNavigate(`/lessons/${slug}`)}
        >
          Back to Editor
        </button>
      </div>
      <div className="preview-meta">
        <span className="badge badge-draft">Preview Mode</span>
        <span>Difficulty: {lesson.difficulty}</span>
        <span>~{lesson.estimated_minutes} min</span>
      </div>
      <p className="preview-description">{lesson.description}</p>
      {lesson.sections.map((section) => (
        <div key={section.id} className="preview-section">
          <h2>{section.title}</h2>
          <span className="section-type">{section.kind}</span>
          {section.body.map((para, i) => (
            <p key={i}>{para}</p>
          ))}
          {section.element_symbol && (
            <div className="spotlight-ref">
              Element: <strong>{section.element_symbol}</strong>
            </div>
          )}
          {section.molecule_input && (
            <div className="spotlight-ref">
              Molecule: <strong>{section.molecule_input}</strong>
            </div>
          )}
          {section.questions.length > 0 && (
            <div className="preview-questions">
              {section.questions.map((q) => (
                <div key={q.id} className="preview-question">
                  <p className="question-prompt">{q.prompt}</p>
                  {q.options.length > 0 && (
                    <ul className="question-options">
                      {q.options.map((opt, i) => (
                        <li key={i}>{opt}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// --- App ---

export default function App() {
  const [page, setPage] = useState<Page>(parseHash);
  const [listData, setListData] = useState<AdminLessonList | null>(null);
  const [authError, setAuthError] = useState(false);

  const go = useCallback((hash: string) => {
    navigate(hash);
    setPage(parseHash());
  }, []);

  useEffect(() => {
    const onHash = () => setPage(parseHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Fetch lesson list when needed.
  useEffect(() => {
    if (page.kind === 'dashboard' || page.kind === 'list') {
      api
        .listLessons()
        .then(setListData)
        .catch((err) => {
          if (err instanceof api.ApiError && err.status === 401) {
            setAuthError(true);
          }
        });
    }
  }, [page.kind]);

  const handlePublish = async (slug: string) => {
    await api.publishLesson(slug);
    const data = await api.listLessons();
    setListData(data);
  };
  const handleUnpublish = async (slug: string) => {
    await api.unpublishLesson(slug);
    const data = await api.listLessons();
    setListData(data);
  };

  if (authError) return <AuthGate />;
  if (page.kind === 'dashboard')
    return (
      <Shell>
        <Dashboard data={listData} onNavigate={go} />
      </Shell>
    );
  if (page.kind === 'list')
    return (
      <Shell>
        <LessonList
          data={listData}
          onNavigate={go}
          onPublish={handlePublish}
          onUnpublish={handleUnpublish}
        />
      </Shell>
    );
  if (page.kind === 'edit')
    return (
      <Shell>
        <LessonEditor
          slug={page.slug}
          onSave={() => go('/lessons')}
          onCancel={() => go('/lessons')}
        />
      </Shell>
    );
  if (page.kind === 'preview')
    return (
      <Shell>
        <PreviewPage slug={page.slug} onNavigate={go} />
      </Shell>
    );
  return null;
}
