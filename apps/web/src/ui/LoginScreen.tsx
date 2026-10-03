import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { GoogleSignInError, GOOGLE_SIGN_IN_BUTTON_HOST_ID } from '../auth/googleSignIn';

export function LoginScreen() {
  const auth = useAuth();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const attached = useRef(false);
  const [buttonError, setButtonError] = useState<string | null>(null);
  useEffect(() => {
    if (attached.current || !hostRef.current) return;
    attached.current = true;
    try {
      auth.provider.attach(hostRef.current, (credential) => void auth.exchangeCredential(credential));
    } catch (err) {
      setButtonError(err instanceof GoogleSignInError ? err.message : 'Google Sign-In is unavailable. Please try again.');
    }
  }, [auth.provider, auth.exchangeCredential]);
  return (
    <div className="center">
      <main className="auth-card" aria-labelledby="login-title">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">C</div>
          <div><span className="brand">Chemora</span><span className="brand-subtitle">Learn chemistry by doing</span></div>
        </div>
        <div>
          <h1 id="login-title" style={{fontFamily:"'Space Grotesk',sans-serif",fontSize:'2rem',letterSpacing:'-.04em',marginBottom:'.5rem'}}>Your chemistry lab starts here.</h1>
          <p className="tagline">Explore molecules, understand reactions, practice what you learn, and ask your AI tutor when you get stuck.</p>
        </div>
        <div ref={hostRef} id={GOOGLE_SIGN_IN_BUTTON_HOST_ID} className="google-button-host" data-testid="google-sign-in-host" />
        {auth.state === 'loading' ? <p className="status" data-testid="signing-in">Signing you in…</p> : null}
        {buttonError ? <p className="error" role="alert">{buttonError}</p> : null}
        {auth.errorMessage ? <p className="error" role="alert">{auth.errorMessage}</p> : null}
        <p className="help muted">Sign in with Google to keep your lessons and progress synced.</p>
      </main>
    </div>
  );
}