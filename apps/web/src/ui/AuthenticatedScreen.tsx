import type { CurrentUser } from '../api/types';

export interface AuthenticatedScreenProps {
  user: CurrentUser;
  onSignOut: () => Promise<void>;
}

/**
 * Minimal placeholder shown after authentication. Proves the end-to-end flow
 * (session check → authenticated UI → logout). The real Chemora learning
 * experience belongs to later milestones.
 */
export function AuthenticatedScreen({ user, onSignOut }: AuthenticatedScreenProps) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">Chemora</span>
        <button type="button" className="button" onClick={() => void onSignOut()}>
          Sign out
        </button>
      </header>
      <main className="main">
        <h1>Welcome, {user.display_name ?? user.email}</h1>
        <p className="muted">{user.email}</p>
        <p className="note">You are signed in to Chemora.</p>
      </main>
    </div>
  );
}