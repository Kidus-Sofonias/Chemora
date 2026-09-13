/**
 * Google Identity Services (GIS) client integration.
 *
 * The default provider renders Google's official "Sign in with Google" button
 * (loaded from https://accounts.google.com/gsi/client) and delivers the
 * Google ID token as the sign-in `credential`. The Chemora backend remains
 * the sole authority: it verifies the credential server-side and establishes
 * the Chemora session. The client never treats the Google credential as an
 * authenticated Chemora session.
 *
 * Tests inject a mock provider, so no live Google account is required.
 */

export const GOOGLE_SIGN_IN_BUTTON_HOST_ID = 'chemora-google-sign-in';

export class GoogleSignInError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'GoogleSignInError';
  }
}

/**
 * Port for obtaining a Google credential. Everything above this boundary
 * (auth service, provider, UI, tests) depends only on this interface.
 */
export interface GoogleSignInProvider {
  /** The configured public Google OAuth client id, or null when unset. */
  readonly clientId: string | null;
  /**
   * Render the official Google sign-in button inside `host`, then call
   * `onCredential` with the Google ID token once the user completes the flow.
   */
  attach(host: HTMLElement, onCredential: (credential: string) => void): void;
}

// --- Default provider (real Google GIS client) ---
// The official GIS client script is loaded in index.html from
// https://accounts.google.com/gsi/client; the provider uses the global
// `google.accounts.id` object it exposes.

/** Minimal typing for the GIS client's google.accounts.id surface we use. */
interface GsiAccountsId {
  displaySignInButton?: (
    options: { clientId: string; scope: string; renderTo: string },
    callbacks?: { onSignIn?: (credential: string) => void },
  ) => void;
}

interface GoogleWindow {
  google?: { accounts?: { id?: GsiAccountsId } };
}

/** Resolve the public Google client id. Returns null for unset/placeholder. */
export function resolveGoogleClientId(): string | null {
  const raw = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
  const value = typeof raw === 'string' ? raw.trim() : '';
  if (!value) return null;
  if (value === 'your-google-client-id.apps.googleusercontent.com') return null;
  return value;
}

/**
 * Production provider. Thin adapter over Google's official GIS client. This
 * is the only integration point that talks to Google's client; it is mocked
 * in the automated test suite (the boundary around it is tested).
 */
export class DefaultGoogleSignInProvider implements GoogleSignInProvider {
  readonly clientId: string | null;

  constructor(clientId?: string) {
    this.clientId = clientId ?? resolveGoogleClientId();
  }

  attach(host: HTMLElement, onCredential: (credential: string) => void): void {
    if (!this.clientId) {
      throw new GoogleSignInError(
        'Google Sign-In is not configured. Add VITE_GOOGLE_CLIENT_ID.',
      );
    }
    const accountsId = (window as GoogleWindow).google?.accounts?.id;
    if (!accountsId || typeof accountsId.displaySignInButton !== 'function') {
      throw new GoogleSignInError('Google Sign-In could not start. Please try again.');
    }
    accountsId.displaySignInButton(
      {
        clientId: this.clientId,
        scope: 'profile email openid',
        renderTo: host.id,
      },
      {
        onSignIn: (credential: string) => {
          if (credential && typeof credential === 'string') {
            onCredential(credential);
          }
        },
      },
    );
  }
}