import { ApiClient } from './api/apiClient';
import { ApiAuthService, type AuthService } from './auth/AuthService';
import { AuthProvider } from './auth/AuthProvider';
import type { GoogleSignInProvider } from './auth/googleSignIn';
import { DefaultGoogleSignInProvider } from './auth/googleSignIn';
import { RootRouter } from './ui/AuthGate';

export interface AppDeps {
  /** Inject for tests; production uses the real API-backed service. */
  service?: AuthService;
  /** Inject for tests; production uses the Google GIS client provider. */
  provider?: GoogleSignInProvider;
}

export function App(deps: AppDeps = {}) {
  const api = new ApiClient();
  const service = deps.service ?? new ApiAuthService(api);
  const provider = deps.provider ?? new DefaultGoogleSignInProvider();

  return (
    <AuthProvider service={service} provider={provider}>
      <RootRouter />
    </AuthProvider>
  );
}