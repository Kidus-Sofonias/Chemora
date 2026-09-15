import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type { ElementDetail, ElementSummary } from '../api/types';

/**
 * Element Explorer state machine.
 *
 * The periodic table loads once (118 elements is small and read-only).
 * Selecting an element fetches its computed electron structure on demand and
 * caches it, so re-selecting is instant. Errors are classified:
 *   - unknown-element  → the identifier matched no element (404)
 *   - network-error    → the backend is unreachable
 *   - server-error     → the backend failed
 * Nothing retries automatically (no loops).
 */
export type ElementListState =
  | { kind: 'loading' }
  | { kind: 'error'; kind2: 'network' | 'server'; message: string }
  | { kind: 'ready'; elements: ElementSummary[] };

export type ElementDetailState =
  | { kind: 'idle' }
  | { kind: 'loading'; symbol: string }
  | { kind: 'success'; detail: ElementDetail }
  | { kind: 'unknown-element'; symbol: string; message: string }
  | { kind: 'network-error'; symbol: string; message: string }
  | { kind: 'server-error'; symbol: string; message: string };

const NETWORK_MESSAGE =
  'Cannot reach the Chemora server. Check your connection and try again.';
const SERVER_MESSAGE =
  'The element service hit a problem. Please try again in a moment.';

export function useElements(api: ApiClient) {
  const [list, setList] = useState<ElementListState>({ kind: 'loading' });
  const [detail, setDetail] = useState<ElementDetailState>({ kind: 'idle' });
  const cache = useRef(new Map<string, ElementDetail>());
  const requestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getElements()
      .then((result) => {
        if (!cancelled) {
          setList({ kind: 'ready', elements: result.elements });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && err.isNetworkError) {
          setList({ kind: 'error', kind2: 'network', message: NETWORK_MESSAGE });
        } else {
          setList({ kind: 'error', kind2: 'server', message: SERVER_MESSAGE });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const selectElement = useCallback(
    async (summary: ElementSummary) => {
      const symbol = summary.symbol;
      const cached = cache.current.get(symbol);
      if (cached) {
        setDetail({ kind: 'success', detail: cached });
        return;
      }
      const id = ++requestId.current;
      setDetail({ kind: 'loading', symbol });
      try {
        const fetched = await api.getElement(symbol);
        cache.current.set(symbol, fetched);
        if (id === requestId.current) {
          setDetail({ kind: 'success', detail: fetched });
        }
      } catch (err) {
        if (id !== requestId.current) {
          return; // a newer selection superseded this request
        }
        if (err instanceof ApiError && err.status === 404) {
          setDetail({
            kind: 'unknown-element',
            symbol,
            message: err.message ?? 'That element could not be found.',
          });
        } else if (err instanceof ApiError && err.isNetworkError) {
          setDetail({
            kind: 'network-error',
            symbol,
            message: NETWORK_MESSAGE,
          });
        } else {
          setDetail({ kind: 'server-error', symbol, message: SERVER_MESSAGE });
        }
      }
    },
    [api],
  );

  return { list, detail, selectElement };
}
