import type { ReactNode } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { LoginScreen } from './LoginScreen';
import { AuthenticatedScreen } from './AuthenticatedScreen';
import { ExplorerSection } from './ExplorerPage';

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

/** The application root: switches on the current auth state. */
export function RootRouter() {
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
  return (
    <AuthenticatedScreen user={auth.user!} onSignOut={auth.signOut}>
      <ExplorerSection />
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