import type { CurrentUser } from '../api/types';
import type { ReactNode } from 'react';

export interface AuthenticatedScreenProps {
  user: CurrentUser;
  onSignOut: () => Promise<void>;
  /** Feature content rendered inside the authenticated app shell. */
  children?: ReactNode;
}

/**
 * The authenticated application shell. Feature content (e.g. the Chemistry
 * Explorer) is passed as children so the shell stays stable across features.
 */
export function AuthenticatedScreen({ user, onSignOut, children }: AuthenticatedScreenProps) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">Chemora</span>
        <div className="topbar-right">
          <span className="muted" data-testid="signed-in-user">
            Welcome, {user.display_name ?? user.email}
          </span>
          <button type="button" className="button" onClick={() => void onSignOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main className="main">
        <p className="muted" data-testid="signed-in-email">{user.email}</p>
        {children ?? (
          <p className="note">You are signed in to Chemora.</p>
        )}
      </main>
    </div>
  );
}