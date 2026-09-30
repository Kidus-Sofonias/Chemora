import { useCallback, useEffect, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type { DashboardResponse } from '../api/types';

/** Dashboard data-loading state (mirrors the useLearning pattern). */
export type DashboardState =
  | { kind: 'loading' }
  | { kind: 'error'; network: boolean; message: string }
  | { kind: 'ready'; dashboard: DashboardResponse };

const NETWORK_MESSAGE =
  'Cannot reach the Chemora server. Check your connection and try again.';
const SERVER_MESSAGE =
  'The dashboard hit a problem. Please try again in a moment.';

/**
 * Only structured backend errors (`detail.code` + `detail.message`) carry a
 * message intended for users; anything else is replaced by a generic fallback.
 */
function userFacingMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.isNetworkError) {
      return NETWORK_MESSAGE;
    }
    if (err.code !== null && err.message) {
      return err.message;
    }
  }
  return fallback;
}

/**
 * Loads the student dashboard (`GET /api/v1/learning/dashboard`). The dashboard
 * is read-only and composed on the backend from the catalog + existing progress;
 * this hook only classifies transport vs server errors and exposes `refresh`.
 */
export function useDashboard(api: ApiClient) {
  const [state, setState] = useState<DashboardState>({ kind: 'loading' });

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const dashboard = await api.getDashboard();
      setState({ kind: 'ready', dashboard });
    } catch (err: unknown) {
      setState({
        kind: 'error',
        network: err instanceof ApiError && err.isNetworkError,
        message: userFacingMessage(err, SERVER_MESSAGE),
      });
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, refresh: load };
}
