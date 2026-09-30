import { useApiClient } from '../api/apiContext';
import { useDashboard } from '../learning/useDashboard';
import type { DashboardResponse, DashboardSectionProgress } from '../api/types';
import './dashboard.css';

export interface DashboardPageProps {
  /** Launch a lesson in the Learn section (deep-opening it). */
  onStartLesson: (slug: string) => void;
  /** Switch to the Learn catalog without opening a specific lesson. */
  onOpenCatalog: () => void;
}

/**
 * M43 student dashboard.
 *
 * Renders the recommended lesson, continue-learning + recent-lesson lists,
 * progress by topic, and a practice/results summary — all from the read-only
 * dashboard response composed on the backend from the catalog + existing
 * progress. An authenticated user with no progress sees the empty/new-user
 * state instead.
 */
export function DashboardPage({ onStartLesson, onOpenCatalog }: DashboardPageProps) {
  const api = useApiClient();
  const { state, refresh } = useDashboard(api);

  if (state.kind === 'loading') {
    return (
      <p className="status" role="status" data-testid="dashboard-loading">
        Loading your dashboard…
      </p>
    );
  }
  if (state.kind === 'error') {
    return (
      <div className="card error-card" role="alert" data-testid="dashboard-error">
        <h2>Having trouble</h2>
        <p className="error">
          {state.network ? 'Connection problem' : 'Something went wrong'}
        </p>
        <p className="muted">{state.message}</p>
        <button type="button" className="button" onClick={() => void refresh()}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <DashboardLayout
      dashboard={state.dashboard}
      onStartLesson={onStartLesson}
      onOpenCatalog={onOpenCatalog}
    />
  );
}

function DashboardLayout({
  dashboard,
  onStartLesson,
  onOpenCatalog,
}: {
  dashboard: DashboardResponse;
  onStartLesson: (slug: string) => void;
  onOpenCatalog: () => void;
}) {
  const started = dashboard.totals.started;
  return (
    <section className="dashboard" aria-labelledby="dashboard-title" data-testid="dashboard">
      <header className="dashboard-head">
        <h1 id="dashboard-title">My Dashboard</h1>
        <p className="muted">Pick up where you left off, or start the next lesson.</p>
      </header>

      <RecommendedCard dashboard={dashboard} onStartLesson={onStartLesson} />

      {started === 0 ? (
        <EmptyState
          recommended={dashboard.recommended}
          onStartLesson={onStartLesson}
          onOpenCatalog={onOpenCatalog}
        />
      ) : null}

      <ContinueSection sections={dashboard.sections} onStartLesson={onStartLesson} />
      <RecentSection sections={dashboard.sections} onStartLesson={onStartLesson} />
      <TopicSection topics={dashboard.topics} />
      <PracticeSummary dashboard={dashboard} onStartLesson={onStartLesson} />

      <QuickAccessRail
        dashboard={dashboard}
        onStartLesson={onStartLesson}
        onOpenCatalog={onOpenCatalog}
      />
    </section>
  );
}

function RecommendedCard({
  dashboard,
  onStartLesson,
}: {
  dashboard: DashboardResponse;
  onStartLesson: (slug: string) => void;
}) {
  const rec = dashboard.recommended;
  if (!rec) {
    return null;
  }
  const isActive = dashboard.sections.some((s) => s.lesson_slug === rec.lesson_slug);
  const label = isActive ? 'Continue lesson' : 'Start lesson';
  return (
    <article className="card recommended-card" data-testid="dashboard-recommended" aria-label="Recommended next lesson">
      <h2>Recommended next</h2>
      <p className="muted">{dashboard.recommended_reason}</p>
      <h3>
        {rec.title}
        <span className="help muted">
          {' '}
          ({rec.subject} · {rec.estimated_minutes} min)
        </span>
      </h3>
      {rec.objectives.length > 0 ? (
        <ul className="objectives">
          {rec.objectives.map((objective) => (
            <li key={objective}>{objective}</li>
          ))}
        </ul>
      ) : null}
      <div className="actions">
        <button
          type="button"
          className="button"
          data-testid="dashboard-recommended-start"
          onClick={() => onStartLesson(rec.lesson_slug)}
        >
          {label}
        </button>
      </div>
    </article>
  );
}

function EmptyState({
  recommended,
  onStartLesson,
  onOpenCatalog,
}: {
  recommended: DashboardResponse['recommended'];
  onStartLesson: (slug: string) => void;
  onOpenCatalog: () => void;
}) {
  return (
    <div className="card empty-state" data-testid="dashboard-empty">
      <h2>Start your learning journey</h2>
      <p className="muted">
        You haven't started any lessons yet. Your progress, recommendations, and
        practice results will appear here as you go.
      </p>
      <div className="actions">
        {recommended ? (
          <button
            type="button"
            className="button"
            data-testid="dashboard-empty-start"
            onClick={() => onStartLesson(recommended.lesson_slug)}
          >
            Start {recommended.title}
          </button>
        ) : null}
        <button type="button" className="button" onClick={() => onOpenCatalog()}>
          Browse lessons
        </button>
      </div>
    </div>
  );
}

function LessonRow({
  lesson,
  onStartLesson,
  showProgress = true,
}: {
  lesson: DashboardSectionProgress;
  onStartLesson: (slug: string) => void;
  showProgress?: boolean;
}) {
  const label = lesson.completed
    ? 'Review lesson'
    : lesson.progress_percent > 0
      ? 'Continue lesson'
      : 'Start lesson';
  return (
    <li
      className="dashboard-lesson"
      data-testid={`dashboard-lesson-${lesson.lesson_slug}`}
    >
      <div className="dashboard-lesson-main">
        <h4>{lesson.title}</h4>
        <p className="help muted">
          {lesson.subject} · {lesson.difficulty} · {lesson.estimated_minutes} min
        </p>
        {showProgress ? (
          <div
            className="progress-bar"
            role="img"
            aria-label={`${lesson.progress_percent}% complete`}
          >
            <div className="progress-bar-fill" style={{ width: `${lesson.progress_percent}%` }} />
          </div>
        ) : null}
        {lesson.needs_review ? (
          <span className="badge needs-review" data-testid={`needs-review-${lesson.lesson_slug}`}>
            Needs review
          </span>
        ) : null}
      </div>
      <button type="button" className="button" onClick={() => onStartLesson(lesson.lesson_slug)}>
        {label}
      </button>
    </li>
  );
}

function SectionList({
  title,
  testid,
  sections,
  onStartLesson,
}: {
  title: string;
  testid: string;
  sections: DashboardSectionProgress[];
  onStartLesson: (slug: string) => void;
}) {
  if (sections.length === 0) {
    return null;
  }
  return (
    <section className="dashboard-block" data-testid={testid}>
      <h2>{title}</h2>
      <ul className="dashboard-lesson-list">
        {sections.map((lesson) => (
          <LessonRow key={lesson.lesson_slug} lesson={lesson} onStartLesson={onStartLesson} />
        ))}
      </ul>
    </section>
  );
}

function ContinueSection({
  sections,
  onStartLesson,
}: {
  sections: DashboardSectionProgress[];
  onStartLesson: (slug: string) => void;
}) {
  return (
    <SectionList
      title="Continue learning"
      testid="dashboard-continue"
      sections={sections.filter((s) => !s.completed)}
      onStartLesson={onStartLesson}
    />
  );
}

function RecentSection({
  sections,
  onStartLesson,
}: {
  sections: DashboardSectionProgress[];
  onStartLesson: (slug: string) => void;
}) {
  return (
    <SectionList title="Recent lessons" testid="dashboard-recent" sections={sections} onStartLesson={onStartLesson} />
  );
}

function TopicSection({ topics }: { topics: DashboardResponse['topics'] }) {
  return (
    <section className="dashboard-block" data-testid="dashboard-topics">
      <h2>Progress by topic</h2>
      <ul className="topic-list">
        {topics.map((topic) => (
          <li key={topic.subject} className="topic-item" data-testid={`topic-${topic.subject}`}>
            <div className="topic-head">
              <span>{topic.subject}</span>
              <span className="help muted">
                {topic.completed}/{topic.lesson_count} lessons · {topic.progress_percent}%
              </span>
            </div>
            <div
              className="progress-bar"
              role="img"
              aria-label={`${topic.progress_percent}% topic progress`}
            >
              <div className="progress-bar-fill" style={{ width: `${topic.progress_percent}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PracticeSummary({
  dashboard,
  onStartLesson,
}: {
  dashboard: DashboardResponse;
  onStartLesson: (slug: string) => void;
}) {
  const needsReview = dashboard.sections.filter((s) => s.needs_review);
  return (
    <section className="dashboard-block" data-testid="dashboard-practice">
      <h2>Practice results</h2>
      <dl className="practice-stats">
        <div>
          <dt>Started lessons</dt>
          <dd data-testid="practice-started">{dashboard.totals.started}</dd>
        </div>
        <div>
          <dt>In progress</dt>
          <dd>{dashboard.totals.in_progress}</dd>
        </div>
        <div>
          <dt>Completed</dt>
          <dd>{dashboard.totals.completed}</dd>
        </div>
        <div>
          <dt>Needs review</dt>
          <dd data-testid="practice-needs-review">{dashboard.totals.needs_review}</dd>
        </div>
      </dl>
      {needsReview.length > 0 ? (
        <p className="help">
          Re-answer questions in lessons marked for review to improve accuracy.
        </p>
      ) : null}
      {needsReview.length > 0 ? (
        <ul className="dashboard-lesson-list">
          {needsReview.map((lesson) => (
            <LessonRow
              key={lesson.lesson_slug}
              lesson={lesson}
              onStartLesson={onStartLesson}
              showProgress={false}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function QuickAccessRail({
  dashboard,
  onStartLesson,
  onOpenCatalog,
}: {
  dashboard: DashboardResponse;
  onStartLesson: (slug: string) => void;
  onOpenCatalog: () => void;
}) {
  const rec = dashboard.recommended;
  return (
    <nav className="dashboard-rail" aria-label="Quick access" data-testid="dashboard-rail">
      <button type="button" className="button" onClick={() => onOpenCatalog()}>
        Lessons catalog
      </button>
      {rec ? (
        <button type="button" className="button" onClick={() => onStartLesson(rec.lesson_slug)}>
          {dashboard.sections.some((s) => s.lesson_slug === rec.lesson_slug)
            ? 'Continue recommended'
            : 'Start recommended'}
        </button>
      ) : null}
      <a href="#dashboard-topics" className="button">
        Progress by topic
      </a>
      <a href="#dashboard-practice" className="button">
        Practice results
      </a>
    </nav>
  );
}
