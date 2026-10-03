import type { CurrentUser } from '../api/types';
import type { ReactNode } from 'react';

export interface AuthenticatedScreenProps {
  user: CurrentUser;
  onSignOut: () => Promise<void>;
  children?: ReactNode;
}

export function AuthenticatedScreen({ user, onSignOut, children }: AuthenticatedScreenProps) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Chemora navigation">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">C</div>
          <div>
            <span className="brand">Chemora</span>
            <span className="brand-subtitle">Learn chemistry by doing</span>
          </div>
        </div>
        <div className="sidebar-user">
          <div className="avatar">
            {(user.display_name ?? user.email).charAt(0).toUpperCase()}
          </div>
          <div className="sidebar-user-copy">
            <strong>{user.display_name ?? 'Student'}</strong>
            <span>{user.email}</span>
          </div>
        </div>
        <div className="sidebar-tip">
          <span className="tip-dot" />
          <span>Everything you explore is powered by ChemEngine.</span>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="mobile-brand">
            <div className="brand-mark" aria-hidden="true">C</div>
            <span className="brand">Chemora</span>
          </div>
          <div className="topbar-context">
            <span className="eyebrow">CHEMISTRY LAB</span>
            <span className="topbar-title">Explore, learn, experiment</span>
          </div>
          <div className="topbar-actions">
            <div className="topbar-avatar" title={user.display_name ?? user.email}>
              {(user.display_name ?? user.email).charAt(0).toUpperCase()}
            </div>
            <button type="button" className="button ghost-button" onClick={() => void onSignOut()}>
              Sign out
            </button>
          </div>
        </header>
        <main className="main">{children ?? <p className="note">You are signed in to Chemora.</p>}</main>
        <footer className="mobile-footer">
          <span>CHEMORA</span>
          <span>Student chemistry workspace</span>
        </footer>
      </div>
    </div>
  );
}
