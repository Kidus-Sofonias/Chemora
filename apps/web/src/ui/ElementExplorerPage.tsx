import { useMemo, useState } from 'react';
import type { ElementSummary } from '../api/types';
import { useElements } from '../elements/useElements';
import { useApiClient } from '../api/apiContext';
import { ElementDetails } from './elements/ElementDetails';
import { PeriodicTable } from './elements/PeriodicTable';

/**
 * The Element Explorer — the second Chemora feature surface.
 *
 * The periodic table (loaded once from the backend/ChemEngine dataset) is the
 * navigation surface; selecting an element fetches its engine-computed
 * electron structure. Search filters the same engine-provided list by name,
 * symbol, or atomic number — it is a UI index, not a second data source.
 */
export function ElementExplorerPage() {
  const api = useApiClient();
  const { list, detail, selectElement } = useElements(api);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<ElementSummary | null>(null);

  const filtered = useMemo(() => {
    if (list.kind !== 'ready') {
      return [];
    }
    const q = query.trim().toLowerCase();
    if (!q) {
      return list.elements;
    }
    return list.elements.filter(
      (el) =>
        el.name.toLowerCase().includes(q) ||
        el.symbol.toLowerCase() === q ||
        el.symbol.toLowerCase().startsWith(q) ||
        String(el.atomic_number) === q,
    );
  }, [list, query]);

  const handleSelect = (element: ElementSummary) => {
    setSelected(element);
    void selectElement(element);
  };

  return (
    <section className="element-explorer" aria-labelledby="element-explorer-title">
      <div className="explorer-head">
        <h2 id="element-explorer-title">Element Explorer</h2>
        <p className="muted">
          Browse the periodic table and explore each element's electron
          configuration — computed deterministically by the Chemora chemistry
          engine.
        </p>
      </div>

      <form className="explorer-form" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="visually-hidden" htmlFor="element-search">
          Search element by name, symbol, or atomic number
        </label>
        <input
          id="element-search"
          className="explorer-input"
          type="search"
          name="query"
          autoComplete="off"
          placeholder="Search element… e.g. oxygen, Fe, 26"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-describedby="element-search-help"
        />
      </form>
      <p id="element-search-help" className="help muted">
        Search by name (oxygen), symbol (Fe), or atomic number (26).
      </p>

      {list.kind === 'loading' ? (
        <p className="status" role="status" data-testid="elements-loading">
          Loading the periodic table…
        </p>
      ) : null}
      {list.kind === 'error' ? (
        <div className="card error-card" role="alert" data-testid="elements-error">
          <h3>
            {list.kind2 === 'network' ? 'Connection problem' : 'Something went wrong'}
          </h3>
          <p>{list.message}</p>
        </div>
      ) : null}

      {list.kind === 'ready' ? (
        filtered.length === 0 && query.trim() ? (
          <p className="note" role="status" data-testid="elements-no-match">
            No element matches “{query.trim()}”. Try a symbol (O), a name
            (oxygen), or an atomic number (8).
          </p>
        ) : (
          <PeriodicTable
            elements={filtered}
            selectedSymbol={selected?.symbol ?? null}
            onSelect={handleSelect}
          />
        )
      ) : null}

      <div aria-live="polite" className="element-status-region">
        {detail.kind === 'loading' ? (
          <p className="status" role="status" data-testid="element-loading">
            Exploring {detail.symbol}…
          </p>
        ) : null}
        {detail.kind === 'unknown-element' ||
        detail.kind === 'network-error' ||
        detail.kind === 'server-error' ? (
          <div className="card error-card" role="alert" data-testid="element-error">
            <h3>
              {detail.kind === 'unknown-element'
                ? 'Element not found'
                : detail.kind === 'network-error'
                  ? 'Connection problem'
                  : 'Something went wrong'}
            </h3>
            <p>{detail.message}</p>
          </div>
        ) : null}
        {detail.kind === 'success' ? <ElementDetails detail={detail.detail} /> : null}
      </div>
    </section>
  );
}
