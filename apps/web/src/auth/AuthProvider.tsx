import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiError } from '../api/apiClient';
import type { CurrentUser } from '../api/types';
import type { AuthStateKind } from './authState';
import type { AuthService } from './AuthService';
import type { GoogleSignInProvider } from './googleSignIn';

export interface AuthContextValue {
  state: AuthStateKind;
  user: CurrentUser | null;
  errorMessage: string | null;
  provider: GoogleSignInProvider;
  exchangeCredential: (credential: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Re-run the initial session check (e.g. after a network error). */
  retry: () => Promise<void>;
}

interface AuthProviderProps {
  service: AuthService;
  provider: GoogleSignInProvider;
  children: ReactNode;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Centralized authentication state.
 *
 * On mount it checks the existing Chemora session via GET /auth/me and drives
 * the app through loading → authenticated | unauthenticated | error. All user
 * and session decisions come from the backend; nothing here is manufactured
 * from local data.
 */
export function AuthProvider({ service, provider, children }: AuthProviderProps) {
  const [state, setState] = useState<AuthStateKind>('loading');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // Guards against stale async results and duplicate initialization.
  const generation = useRef(0);
  const started = useRef(false);

  const apply = useCallback((next: AuthStateKind, nextUser: CurrentUser | null, nextError: string | null) => {
    setUser(nextUser);
    setErrorMessage(nextError);
    setState(next);
  }, []);

  const checkSession = useCallback(async () => {
    const gen = ++generation.current;
    setState('loading');
    setErrorMessage(null);
    try {
      const u = await service.getCurrentUser();
      if (gen !== generation.current) return;
      apply('authenticated', u, null);
    } catch (err) {
      if (gen !== generation.current) return;
      if (isUnauthorized(err)) {
        apply('unauthenticated', null, null);
      } else if (isNetworkError(err)) {
        apply('error', null, 'Cannot reach the Chemora server. Check your connection and try again.');
      } else {
        apply('error', null, 'Something went wrong while checking your session.');
      }
    }
  }, [service, apply]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void checkSession();
  }, [checkSession]);

  const exchangeCredential = useCallback(async (credential: string) => {
    const gen = ++generation.current;
    setState('loading');
    setErrorMessage(null);
    try {
      const u = await service.exchangeCredential(credential);
      if (gen !== generation.current) return;
      apply('authenticated', u, null);
    } catch (err) {
      if (gen !== generation.current) return;
      apply('unauthenticated', null, userFacingSignInError(err));
    }
  }, [service, apply]);

  const signOut = useCallback(async () => {
    // Revoke the backend session first; always clear local state so the UI
    // never stays "authenticated" when the backend has rejected the session.
    await service.signOut().catch(() => undefined);
    ++generation.current; // ignore any in-flight check/exchange results
    apply('unauthenticated', null, null);
  }, [service, apply]);

  const retry = useCallback(() => checkSession(), [checkSession]);

  const value: AuthContextValue = {
    state,
    user,
    errorMessage,
    provider,
    exchangeCredential,
    signOut,
    retry,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used within an AuthProvider.');
  }
  return value;
}

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.isAuthError;
}

export function isNetworkError(err: unknown): boolean {
  return err instanceof ApiError && err.isNetworkError;
}

function userFacingSignInError(err: unknown): string | null {
  if (err instanceof ApiError) {
    if (err.isAuthError) {
      return 'Sign-in could not be completed. Please check your Google account and try again.';
    }
    if (err.isNetworkError) {
      return 'Could not reach the Chemora server. Your sign-in may not have completed.';
    }
    return 'Sign-in failed. Please try again.';
  }
  return 'Sign-in failed. Please try again.';
}