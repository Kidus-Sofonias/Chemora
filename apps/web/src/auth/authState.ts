/**
 * The distinct authentication states the application can be in.
 *
 *   App starts ──> loading ──> authenticated | unauthenticated
 *                                        │
 *              network failure ──> error (retry)       ──> back to loading
 */
export type AuthStateKind =
  | 'loading'
  | 'unauthenticated'
  | 'authenticated'
  | 'error';