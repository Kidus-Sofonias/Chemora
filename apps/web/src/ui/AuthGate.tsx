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

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (auth.state === 'loading') return <LoadingScreen />;
  if (auth.state === 'error') return <ErrorScreen onRetry={() => void auth.retry()} message={auth.errorMessage} />;
  if (auth.state === 'unauthenticated') return <LoginScreen />;
  return <>{children}</>;
}

type Section = 'dashboard' | 'learn' | 'explore' | 'elements' | 'tutor';

export function RootRouter() {
  const auth = useAuth();
  const [section, setSection] = useState<Section>('dashboard');
  const [selectedLesson, setSelectedLesson] = useState<string | null>(null);

  const navigate = useCallback((next: Section, lesson?: string) => {
    setSection(next);
    setSelectedLesson(lesson ?? null);
  }, []);

  if (auth.state === 'loading') return <LoadingScreen />;
  if (auth.state === 'error') return <ErrorScreen onRetry={() => void auth.retry()} message={auth.errorMessage} />;
  if (auth.state === 'unauthenticated') return <LoginScreen />;

  const nav = (next: Section, lesson?: string) => () => navigate(next, lesson);
  return (
    <AuthenticatedScreen user={auth.user!} onSignOut={auth.signOut}>
      <nav className="section-nav" aria-label="Main navigation">
        <button type="button" className={`button${section === 'dashboard' ? ' active' : ''}`} aria-pressed={section === 'dashboard'} onClick={nav('dashboard')}>Home</button>
        <button type="button" className={`button${section === 'learn' ? ' active' : ''}`} aria-pressed={section === 'learn'} onClick={nav('learn')}>Learn</button>
        <button type="button" className={`button${section === 'explore' ? ' active' : ''}`} aria-pressed={section === 'explore'} onClick={nav('explore')}>Explore</button>
        <button type="button" className={`button${section === 'elements' ? ' active' : ''}`} aria-pressed={section === 'elements'} onClick={nav('elements')}>Elements</button>
        <button type="button" className={`button${section === 'tutor' ? ' active' : ''}`} aria-pressed={section === 'tutor'} onClick={nav('tutor')}>AI Tutor</button>
      </nav>
      {section === 'dashboard' ? (
        <DashboardPage onStartLesson={(slug) => navigate('learn', slug)} onOpenCatalog={() => navigate('learn')} />
      ) : section === 'learn' ? (
        <LearningPage initialLessonSlug={selectedLesson} />
      ) : section === 'explore' ? (
        <ExplorerSection />
      ) : section === 'elements' ? (
        <ElementExplorerPage />
      ) : (
        <TutorPage />
      )}
    </AuthenticatedScreen>
  );
}

function LoadingScreen() {
  return <div className="center"><p className="status" role="status" data-testid="loading-indicator">Loading your chemistry workspace…</p></div>;
}
function ErrorScreen({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return <div className="center"><div className="auth-card"><h2>We hit a connection problem</h2><p className="error" role="alert">{message ?? 'An unexpected error occurred.'}</p><button type="button" className="button primary" onClick={onRetry}>Try again</button></div></div>;
}
