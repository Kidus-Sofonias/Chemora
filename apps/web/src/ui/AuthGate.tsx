import { useCallback, useState } from 'react';
import type { ReactNode } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { LoginScreen } from './LoginScreen';
import { AuthenticatedScreen } from './AuthenticatedScreen';
import { ExplorerSection } from './ExplorerPage';
import { ElementExplorerPage } from './ElementExplorerPage';
import { LearningPage } from './LearningPage';
import { DashboardPage } from './DashboardPage';
import { TutorPage } from './TutorPage';

/**
 * Guards authenticated content behind the auth check.
 *
 * The root renders a placeholder reading session state only after
 * GET /auth/me has resolved, so authenticated content is never shown before
 * the check completes (no flicker). States:
 *   loading        → loading indicator
 *   error          → retry screen (distinct from unauthenticated)
 *   unauthenticated→ login screen
 *   authenticated  → the protected content (children)
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  if (auth.state === 'loading') {
    return <LoadingScreen />;
  }
  if (auth.state === 'error') {
    return <ErrorScreen onRetry={() => void auth.retry()} message={auth.errorMessage} />;
  }
  if (auth.state === 'unauthenticated') {
    return <LoginScreen />;
  }

  // Authenticated content.
  return <>{children}</>;
}

type Section = 'chemistry' | 'dashboard' | 'elements' | 'learn' | 'tutor';

/** The application root: switches on the current auth state. */
export function RootRouter() {
  const auth = useAuth();
  const [section, setSection] = useState<Section>('chemistry');
  const [selectedLesson, setSelectedLesson] = useState<string | null>(null);

  // Centralised section switches: the dashboard is the only entry point that
  // carries a slug into Learn (it auto-opens); every other switch clears it.
  const navigate = useCallback(
    (next: Section, lesson?: string) => {
      setSection(next);
      setSelectedLesson(lesson ?? null);
    },
    [],
  );

  if (auth.state === 'loading') {
    return <LoadingScreen />;
  }
  if (auth.state === 'error') {
    return <ErrorScreen onRetry={() => void auth.retry()} message={auth.errorMessage} />;
  }
  if (auth.state === 'unauthenticated') {
    return <LoginScreen />;
  }
  return (
    <AuthenticatedScreen user={auth.user!} onSignOut={auth.signOut}>
      <nav className="section-nav" aria-label="Explore sections">
        <button
          type="button"
          className={`button${section === 'chemistry' ? ' active' : ''}`}
          aria-pressed={section === 'chemistry'}
          onClick={() => navigate('chemistry')}
        >
          Chemistry
        </button>
        <button
          type="button"
          className={`button${section === 'elements' ? ' active' : ''}`}
          aria-pressed={section === 'elements'}
          onClick={() => navigate('elements')}
        >
          Elements
        </button>
        <button
          type="button"
          className={`button${section === 'learn' ? ' active' : ''}`}
          aria-pressed={section === 'learn'}
          onClick={() => navigate('learn')}
        >
          Learn
        </button>
        <button
          type="button"
          className={`button${section === 'dashboard' ? ' active' : ''}`}
          aria-pressed={section === 'dashboard'}
          onClick={() => navigate('dashboard')}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`button${section === 'tutor' ? ' active' : ''}`}
          aria-pressed={section === 'tutor'}
          onClick={() => navigate('tutor')}
        >
          Tutor
        </button>
      </nav>
      {section === 'chemistry' ? (
        <ExplorerSection />
      ) : section === 'dashboard' ? (
        <DashboardPage
          onStartLesson={(slug) => navigate('learn', slug)}
          onOpenCatalog={() => navigate('learn')}
        />
      ) : section === 'elements' ? (
        <ElementExplorerPage />
      ) : section === 'learn' ? (
        <LearningPage initialLessonSlug={selectedLesson} />
      ) : (
        <TutorPage />
      )}
    </AuthenticatedScreen>
  );
}


function LoadingScreen() {
  return (
    <div className="center">
      <p className="status" role="status" data-testid="loading-indicator">
        Loading…
      </p>
    </div>
  );
}

function ErrorScreen({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="center">
      <h2>Having trouble</h2>
      <p className="error" role="alert">{message ?? 'An unexpected error occurred.'}</p>
      <button type="button" className="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}