import { useCallback, useRef, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type {
  ChemistryExplainResponse,
  ChemistryExploreResult,
} from '../api/types';

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

/**
 * Explain states. `idle` until the user requests an explanation; `success`
 * holds the full explain response (facts + explanation). Error sub-types let
 * the UI render the right recovery affordance.
 */
export type ExplainState =
  | { kind: 'idle' }
  | { kind: 'loading'; input: string }
  | { kind: 'success'; input: string; answer: ChemistryExplainResponse }
  | {
      kind: 'error';
      input: string;
      message: string;
      code: string | null;
      auth?: boolean;
    };

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
 *
 * The explain flow lives in the same machine so the UI can read a single
 * `explainState` and toggle `learningMode` alongside exploration.
 */
export function useExplorer(api: ApiClient) {
  const [state, setState] = useState<ExplorerState>({ kind: 'idle' });
  const inFlight = useRef(false);
  const lastSuccess = useRef<string | null>(null);

  const [explainState, setExplainState] =
    useState<ExplainState>({ kind: 'idle' });
  const [learningMode, setLearningMode] = useState(true);
  const explainInFlight = useRef(false);

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

  const explain = useCallback(
    async (input: string) => {
      if (!input || explainInFlight.current) {
        return;
      }
      explainInFlight.current = true;
      setExplainState({ kind: 'loading', input });
      try {
        const answer = await api.explainMolecule(input, learningMode);
        setExplainState({ kind: 'success', input, answer });
      } catch (err) {
        if (err instanceof ApiError && err.status === 422) {
          setExplainState({
            kind: 'error',
            input,
            message: err.message ?? 'That molecule cannot be explained.',
            code: err.code,
          });
        } else if (err instanceof ApiError && err.isNetworkError) {
          setExplainState({
            kind: 'error',
            input,
            message: NETWORK_MESSAGE,
            code: null,
          });
        } else if (err instanceof ApiError && err.isAuthError) {
          setExplainState({
            kind: 'error',
            input,
            message: 'Sign in is required to explain molecules.',
            code: err.code,
            auth: true,
          });
        } else {
          setExplainState({
            kind: 'error',
            input,
            message: SERVER_MESSAGE,
            code: null,
          });
        }
      } finally {
        explainInFlight.current = false;
      }
    },
    [api, learningMode],
  );

  const toggleLearningMode = useCallback(() => {
    setLearningMode((m) => !m);
  }, []);

  return { state, explore, explainState, explain, learningMode, toggleLearningMode };
}
