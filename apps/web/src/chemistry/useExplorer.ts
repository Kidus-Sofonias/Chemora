import { useCallback, useRef, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type { ChemistryExploreResult } from '../api/types';

/**
 * Explorer states. Distinct kinds let the UI treat:
 *   - chemistry validation errors (the input is not recognizable chemistry)
 *   - server errors (the backend failed)
 *   - network errors (the backend is unreachable)
 * differently, instead of collapsing everything into one message.
 */
export type ExplorerState =
  | { kind: 'idle' }
  | { kind: 'loading'; input: string }
  | { kind: 'success'; input: string; result: ChemistryExploreResult }
  | { kind: 'chemistry-error'; input: string; message: string }
  | { kind: 'server-error'; input: string; message: string }
  | { kind: 'network-error'; input: string; message: string };

const NETWORK_MESSAGE =
  'Cannot reach the Chemora server. Check your connection and try again.';
const SERVER_MESSAGE =
  'The chemistry service hit a problem. Please try again in a moment.';

/**
 * Explorer state machine.
 *
 * - A request for the input already shown is skipped (no repeated requests).
 * - A request is ignored while one is already in flight.
 * - Errors are classified but never retried automatically (no loops).
 */
export function useExplorer(api: ApiClient) {
  const [state, setState] = useState<ExplorerState>({ kind: 'idle' });
  const inFlight = useRef(false);
  const lastSuccess = useRef<string | null>(null);

  const explore = useCallback(
    async (rawInput: string) => {
      const input = rawInput.trim();
      if (!input || inFlight.current) {
        return;
      }
      if (lastSuccess.current === input) {
        return; // already showing this exact result
      }

      inFlight.current = true;
      setState({ kind: 'loading', input });
      try {
        const result = await api.exploreChemistry(input);
        lastSuccess.current = input;
        setState({ kind: 'success', input, result });
      } catch (err) {
        if (err instanceof ApiError && err.status === 422) {
          // The backend told us the input is not usable chemistry.
          setState({
            kind: 'chemistry-error',
            input,
            message: err.message ?? 'That input could not be analysed.',
          });
        } else if (err instanceof ApiError && err.isNetworkError) {
          setState({ kind: 'network-error', input, message: NETWORK_MESSAGE });
        } else {
          setState({ kind: 'server-error', input, message: SERVER_MESSAGE });
        }
      } finally {
        inFlight.current = false;
      }
    },
    [api],
  );

  return { state, explore };
}