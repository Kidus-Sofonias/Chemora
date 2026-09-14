import { useState, type FormEvent } from 'react';
import { useApiClient } from '../api/apiContext';
import { useExplorer, type ExplorerState } from '../chemistry/useExplorer';
import { ExplorerResult } from './ExplorerResult';

/**
 * The Chemistry Explorer — the first Chemora feature surface.
 *
 * Identity is shown for every input; structure and bond-derived properties
 * are shown only when the backend reports a real structure. Everything
 * displayed is computed by ChemEngine.
 */
export function ExplorerSection() {
  const api = useApiClient();
  const { state, explore } = useExplorer(api);
  const [value, setValue] = useState('');

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void explore(value);
  };

  const busy = state.kind === 'loading';

  return (
    <section className="explorer" aria-labelledby="explorer-title">
      <div className="explorer-head">
        <h2 id="explorer-title">Chemistry Explorer</h2>
        <p className="muted">
          Enter a molecular formula, SMILES, InChI, or a common name to explore
          its chemistry. Results are computed by the Chemora chemistry engine.
        </p>
      </div>

      <form className="explorer-form" onSubmit={handleSubmit} noValidate>
        <label className="visually-hidden" htmlFor="explorer-input">
          Molecule, formula, or SMILES
        </label>
        <input
          id="explorer-input"
          className="explorer-input"
          type="text"
          name="input"
          autoComplete="off"
          spellCheck={false}
          placeholder="e.g. H2O, CCO, ethanol, InChI=1S/…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={busy}
          aria-describedby="explorer-help"
        />
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? 'Exploring…' : 'Explore'}
        </button>
      </form>
      <p id="explorer-help" className="help muted">
        Examples: H2O · CO2 · C6H6 · ethanol · CH3COOH · CCO
      </p>

      <div aria-live="polite" aria-busy={busy} className="explorer-status-region">
        {state.kind === 'loading' ? (
          <p className="status" role="status" data-testid="explorer-loading">
            Analysing {state.input}…
          </p>
        ) : null}
        <ExplorerFeedback state={state} />
        {state.kind === 'success' ? <ExplorerResult result={state.result} /> : null}
      </div>
    </section>
  );
}

function ExplorerFeedback({ state }: { state: ExplorerState }) {
  const headings: Record<string, string> = {
    'chemistry-error': "We couldn't analyse that input",
    'network-error': 'Connection problem',
    'server-error': 'Something went wrong',
  };
  if (
    state.kind !== 'chemistry-error' &&
    state.kind !== 'network-error' &&
    state.kind !== 'server-error'
  ) {
    return null;
  }
  return (
    <div className="card error-card" role="alert" data-testid="explorer-error">
      <h3>{headings[state.kind]}</h3>
      <p>{state.message}</p>
    </div>
  );
}