import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import {
  GoogleSignInError,
  GOOGLE_SIGN_IN_BUTTON_HOST_ID,
} from '../auth/googleSignIn';

/**
 * Minimal sign-in screen. Renders the official Google sign-in button via the
 * auth provider and forwards the resulting Google credential to the backend.
 */
export function LoginScreen() {
  const auth = useAuth();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const attached = useRef(false);
  const [buttonError, setButtonError] = useState<string | null>(null);

  useEffect(() => {
    if (attached.current) return;
    const host = hostRef.current;
    if (!host) return;
    attached.current = true;
    try {
      auth.provider.attach(host, (credential) => {
        void auth.exchangeCredential(credential);
      });
    } catch (err) {
      setButtonError(
        err instanceof GoogleSignInError
          ? err.message
          : 'Google Sign-In is unavailable. Please try again.',
      );
    }
  }, [auth.provider]);

  return (
    <div className="auth-card">
      <h1 className="brand">Chemora</h1>
      <p className="tagline">Chemistry education &amp; exploration</p>

      <div
        ref={hostRef}
        id={GOOGLE_SIGN_IN_BUTTON_HOST_ID}
        className="google-button-host"
        data-testid="google-sign-in-host"
      />

      {auth.state === 'loading' ? (
        <p className="status" data-testid="signing-in">Signing you in…</p>
      ) : null}

      {buttonError ? (
        <p className="error" role="alert">{buttonError}</p>
      ) : null}
      {auth.errorMessage ? (
        <p className="error" role="alert">{auth.errorMessage}</p>
      ) : null}
    </div>
  );
}