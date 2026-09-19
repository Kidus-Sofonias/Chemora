import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/apiContext';
import { useLearning, userFacingMessage, type ActiveLesson } from '../learning/useLearning';
import type { QuestionPublic, SectionPublic } from '../api/types';
import { ExplorerResult } from './ExplorerResult';
import { ElementDetails } from './elements/ElementDetails';
import './learning.css';

/**
 * The Learning page â€” lesson catalog and lesson viewer (M24).
 *
 * Content (sections, prose, questions) comes from the backend education
 * layer. Chemistry values inside `chemistry_spotlight` sections are fetched
 * live — elements from the element API, molecules from the chemistry explore
 * API — and rendered by the same engine-backed components the Element and
 * Chemistry Explorers use. Answer grading and progress live server-side.
 */
export function LearningPage() {
  const api = useApiClient();
  const { catalog, progressBySlug, current, openLesson, backToCatalog, completeSection, submitAnswer } =
    useLearning(api);

  if (current.kind === 'ready') {
    return (
      <LessonView
        active={current.active}
        onBack={backToCatalog}
        onComplete={completeSection}
        onAnswer={submitAnswer}
      />
    );
  }

  return (
    <section className="learning" aria-labelledby="learning-title">
      <div className="explorer-head">
        <h2 id="learning-title">Learn Chemistry</h2>
        <p className="muted">
          Structured lessons that teach chemistry using live results from the
          Chemora chemistry engine â€” not stored screenshots of it.
        </p>
      </div>

      {current.kind === 'loading' ? (
        <p className="status" role="status" data-testid="lesson-loading">
          Opening lessonâ€¦
        </p>
      ) : null}
      {current.kind === 'error' ? (
        <div className="card error-card" role="alert" data-testid="lesson-error">
          <h3>{current.network ? 'Connection problem' : 'Something went wrong'}</h3>
          <p>{current.message}</p>
          <button type="button" className="button" onClick={() => backToCatalog()}>
            Back to lessons
          </button>
        </div>
      ) : null}

      {catalog.kind === 'loading' ? (
        <p className="status" role="status" data-testid="catalog-loading">
          Loading lessonsâ€¦
        </p>
      ) : null}
      {catalog.kind === 'error' ? (
        <div className="card error-card" role="alert" data-testid="catalog-error">
          <h3>{catalog.network ? 'Connection problem' : 'Something went wrong'}</h3>
          <p>{catalog.message}</p>
        </div>
      ) : null}

      {catalog.kind === 'ready' ? (
        <ul className="lesson-list" data-testid="lesson-list">
          {catalog.lessons.map((lesson) => {
            const progress = progressBySlug[lesson.slug];
            const actionLabel = progress?.completed
              ? 'Review lesson'
              : progress && progress.progress_percent > 0
                ? 'Continue lesson'
                : 'Start lesson';
            return (
              <li key={lesson.slug}>
                <article className="card lesson-card">
                  <h3>{lesson.title}</h3>
                  <p>{lesson.description}</p>
                  <p className="help muted">
                    {lesson.subject} · {lesson.difficulty} · {lesson.estimated_minutes} min
                    · {lesson.section_count} sections · {lesson.question_count} questions
                  </p>
                  {progress ? (
                    <p
                      className="help muted"
                      data-testid={`catalog-progress-${lesson.slug}`}
                    >
                      {progress.completed
                        ? 'Completed ✓'
                        : `${progress.progress_percent}% complete — continue where you left off`}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    className="button"
                    onClick={() => void openLesson(lesson.slug)}
                  >
                    {actionLabel}
                  </button>
                </article>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

interface LessonViewProps {
  active: ActiveLesson;
  onBack: () => void;
  onComplete: (slug: string, sectionId: string) => Promise<void>;
  onAnswer: (slug: string, questionId: string, answer: string) => Promise<unknown>;
}

function LessonView({ active, onBack, onComplete, onAnswer }: LessonViewProps) {
  const { lesson, progress } = active;
  const percent = progress?.progress_percent ?? 0;
  // Resume (M28): focus the first incomplete section, or the first section
  // when the lesson is untouched or already complete.
  const firstIncomplete = lesson.sections.findIndex(
    (section) => !progress?.completed_sections.includes(section.id),
  );
  const [focusIndex, setFocusIndex] = useState(
    firstIncomplete === -1 ? 0 : firstIncomplete,
  );

  const scrollToSection = (index: number) => {
    const section = lesson.sections[index];
    if (!section) {
      return;
    }
    setFocusIndex(index);
    // jsdom has no layout engine — guard for tests.
    document
      .querySelector(`[data-testid="section-${section.id}"]`)
      ?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  };

  // Scroll once on open so a returning student resumes where they left off.
  const resumed = useRef(false);
  useEffect(() => {
    if (resumed.current) {
      return;
    }
    resumed.current = true;
    const section = lesson.sections[focusIndex];
    if (section && focusIndex > 0) {
      document
        .querySelector(`[data-testid="section-${section.id}"]`)
        ?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentSection = lesson.sections[focusIndex];
  const position = lesson.sections.map((s) => s.id).indexOf(currentSection?.id ?? '');
  return (
    <section className="learning lesson-view" aria-labelledby="lesson-title">
      <button type="button" className="button back-button" onClick={onBack}>
        â† All lessons
      </button>
      <header className="lesson-header">
        <h2 id="lesson-title">{lesson.title}</h2>
        <p className="muted">{lesson.description}</p>
        <p className="help muted">
          {lesson.subject} Â· {lesson.difficulty} Â· {lesson.estimated_minutes} min
        </p>
        <div
          className="progress"
          role="progressbar"
          aria-label="Lesson progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          data-testid="lesson-progress"
        >
          <div className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <p className="help muted" data-testid="lesson-progress-label">
          {percent}% complete
          {progress?.completed ? ' â€” lesson complete!' : ''}
        </p>
      </header>

      {lesson.sections.length > 1 ? (
        <nav className="section-nav" aria-label="Section navigation" data-testid="section-nav">
          <button
            type="button"
            className="button"
            disabled={position <= 0}
            onClick={() => scrollToSection(position - 1)}
            data-testid="nav-prev"
          >
            ← Previous section
          </button>
          <span className="help muted" data-testid="nav-position">
            Section {position + 1} of {lesson.sections.length}
            {currentSection ? `: ${currentSection.title}` : ''}
          </span>
          <button
            type="button"
            className="button"
            disabled={position >= lesson.sections.length - 1}
            onClick={() => scrollToSection(position + 1)}
            data-testid="nav-next"
          >
            Next section →
          </button>
        </nav>
      ) : null}

      {lesson.sections.map((section) => (
        <SectionCard
          key={section.id}
          section={section}
          active={active}
          focused={section.id === currentSection?.id}
          onComplete={(id) => onComplete(lesson.slug, id)}
          onAnswer={(qid, answer) => onAnswer(lesson.slug, qid, answer)}
        />
      ))}
    </section>
  );
}



interface SectionCardProps {
  section: SectionPublic;
  active: ActiveLesson;
  focused: boolean;
  onComplete: (sectionId: string) => Promise<void>;
  onAnswer: (questionId: string, answer: string) => Promise<unknown>;
}

function SectionCard({ section, active, focused, onComplete, onAnswer }: SectionCardProps) {
  const completed = active.progress?.completed_sections.includes(section.id) ?? false;
  return (
    <article
      className={`card section-card kind-${section.kind}${focused ? ' section-focused' : ''}`}
      data-testid={`section-${section.id}`}
      aria-current={focused ? 'true' : undefined}
    >
      <h3>
        {section.title}
        {completed ? <span className="done-badge"> done âœ“</span> : null}
      </h3>
      {section.body.map((paragraph, i) => (
        <p key={i}>{paragraph}</p>
      ))}

      {section.kind === 'chemistry_spotlight' && section.element_symbol ? (
        <Spotlight symbol={section.element_symbol} active={active} />
      ) : null}
      {section.kind === 'chemistry_spotlight' && section.molecule_input ? (
        <MoleculeSpotlight input={section.molecule_input} active={active} />
      ) : null}

      {section.questions.map((question) => (
        <PracticeQuestion
          key={question.id}
          question={question}
          active={active}
          onAnswer={onAnswer}
        />
      ))}

      {section.kind === 'practice' ? (
        <PracticeResults questions={section.questions} active={active} />
      ) : null}

      {section.kind !== 'practice' ? (
        <button
          type="button"
          className="button"
          disabled={completed || active.completing !== null}
          onClick={() => void onComplete(section.id)}
          data-testid={`complete-${section.id}`}
        >
          {completed
            ? 'Completed'
            : active.completing === section.id
              ? 'Savingâ€¦'
              : 'Mark section complete'}
        </button>
      ) : null}
    </article>
  );
}

/** Live engine data for a chemistry_spotlight section. */
function Spotlight({
  symbol,
  active,
}: {
  symbol: string;
  active: ActiveLesson;
}) {
  const detail = active.spotlight[symbol];
  if (detail) {
    return (
      <div className="spotlight" data-testid={`spotlight-${symbol}`}>
        <ElementDetails detail={detail} />
      </div>
    );
  }
  if (active.spotlightLoading[symbol]) {
    return (
      <p className="status" role="status" data-testid="spotlight-loading">
        Computing {symbol} with the chemistry engine…
      </p>
    );
  }
  return null;
}

/** One practice question. The server grades; the client only shows results. */
function PracticeQuestion({
  question,
  active,
  onAnswer,
}: {
  question: QuestionPublic;
  active: ActiveLesson;
  onAnswer: (questionId: string, answer: string) => Promise<unknown>;
}) {
  const [choice, setChoice] = useState('');
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const result = active.answers[question.id];
  const pending = active.answering === question.id;
  const answeredCorrect = result?.correct === true;
  const value = question.options.length > 0 ? choice : text;
  const canSubmit = value.trim().length > 0 && !pending && !answeredCorrect;

  const submit = () => {
    if (!canSubmit) {
      return;
    }
    setError(null);
    onAnswer(question.id, value.trim()).catch((err: unknown) => {
      setError(userFacingMessage(err, 'Could not submit the answer.'));
    });
  };

  return (
    <div className="practice" data-testid={`question-${question.id}`}>
      <fieldset>
        <legend>{question.prompt}</legend>
        {question.options.length > 0 ? (
          <div className="options" role="radiogroup" aria-label={question.prompt}>
            {question.options.map((option) => (
              <label key={option} className="option">
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option}
                  checked={choice === option}
                  disabled={answeredCorrect}
                  onChange={() => setChoice(option)}
                />{' '}
                {option}
              </label>
            ))}
          </div>
        ) : (
          <input
            type="text"
            className="explorer-input answer-input"
            aria-label={question.prompt}
            value={text}
            disabled={answeredCorrect}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                submit();
              }
            }}
          />
        )}
      </fieldset>
      <button
        type="button"
        className="button"
        disabled={!canSubmit}
        onClick={submit}
        data-testid={`submit-${question.id}`}
      >
        {answeredCorrect ? 'Correct' : pending ? 'Checkingâ€¦' : 'Check answer'}
      </button>
      {error ? (
        <p className="error" role="alert" data-testid={`question-error-${question.id}`}>
          {error}
        </p>
      ) : null}
      {result ? (
        <div
          className={`feedback ${result.correct ? 'correct' : 'incorrect'}`}
          role="status"
          data-testid={`feedback-${question.id}`}
        >
          <p className="verdict">{result.correct ? 'Correct!' : 'Not quite â€” try again.'}</p>
          <p className="explanation-text">{result.explanation}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Live engine analysis for a molecule spotlight section (M22 explore API). */
function MoleculeSpotlight({
  input,
  active,
}: {
  input: string;
  active: ActiveLesson;
}) {
  const result = active.molecules[input];
  const error = active.moleculeError[input];
  if (result) {
    return (
      <div className="spotlight" data-testid={`molecule-spotlight-${input}`}>
        <ExplorerResult result={result} />
      </div>
    );
  }
  if (active.moleculeLoading[input]) {
    return (
      <p className="status" role="status" data-testid="molecule-loading">
        Analysing {input} with the chemistry engine…
      </p>
    );
  }
  if (error) {
    return (
      <p className="error" role="alert" data-testid="molecule-error">
        {error}
      </p>
    );
  }
  return null;
}

/**
 * Practice summary for a practice section (M25).
 *
 * Every number is derived from server-graded results — the client never
 * decides whether an answer was correct. Progress (correct / needs another
 * look / accuracy) is shown alongside the explanations rather than as a score,
 * and re-answering an incorrect question is always allowed.
 */
function PracticeResults({
  questions,
  active,
}: {
  questions: QuestionPublic[];
  active: ActiveLesson;
}) {
  const attempted = questions.filter((q) => active.answers[q.id] !== undefined);
  if (attempted.length === 0) {
    return null;
  }
  const correct = attempted.filter((q) => active.answers[q.id].correct).length;
  const incorrect = attempted.length - correct;
  const accuracy = Math.round((100 * correct) / attempted.length);
  const finished = incorrect === 0 && attempted.length === questions.length;
  return (
    <div className="practice-results" data-testid="practice-results">
      <h4>Practice results</h4>
      <dl className="practice-stats">
        <div>
          <dt>Attempted</dt>
          <dd data-testid="results-attempted">
            {attempted.length} of {questions.length}
          </dd>
        </div>
        <div>
          <dt>Correct</dt>
          <dd data-testid="results-correct">{correct}</dd>
        </div>
        <div>
          <dt>Needs another look</dt>
          <dd data-testid="results-incorrect">{incorrect}</dd>
        </div>
        <div>
          <dt>Accuracy</dt>
          <dd data-testid="results-accuracy">{accuracy}%</dd>
        </div>
      </dl>
      <p className="help muted">
        {finished
          ? 'Every question is right — read the explanations once more, then move on.'
          : 'Accuracy is one signal, not the goal. Read each explanation and retry anything that needs another look.'}
      </p>
    </div>
  );
}

