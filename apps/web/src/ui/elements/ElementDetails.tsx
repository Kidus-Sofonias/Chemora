import type { ElementDetail } from '../../api/types';

/**
 * Renders an electron-configuration string like "1s2 2s2 2p4" with proper
 * superscripts. Formatting only — the values come from ChemEngine verbatim.
 */
export function ConfigString({ value }: { value: string }) {
  const tokens = value.split(' ');
  return (
    <span className="config-string">
      {tokens.map((token, i) => {
        const match = /^([1-7][spdf])(\d+)$/.exec(token);
        if (!match) {
          return <span key={i}>{token} </span>;
        }
        return (
          <span key={i} className="config-token">
            {match[1]}
            <sup>{match[2]}</sup>{' '}
          </span>
        );
      })}
    </span>
  );
}

/**
 * Standard Hund's-rule box arrangement for one subshell. This is presentation
 * of the engine's occupancy (electrons + capacity): singles spread across the
 * degenerate orbitals before pairing begins.
 */
export function orbitalBoxes(occupancy: {
  electrons: number;
  capacity: number;
}): ('up' | 'down' | null)[] {
  const boxes = occupancy.capacity / 2;
  const singles = Math.min(occupancy.electrons, boxes);
  const pairs = occupancy.electrons - singles;
  const cells: ('up' | 'down' | null)[] = [];
  for (let i = 0; i < boxes; i++) {
    if (i < pairs) {
      cells.push('up', 'down');
    } else if (i < singles) {
      cells.push('up', null);
    } else {
      cells.push(null, null);
    }
  }
  return cells;
}

/** Compact textual form of the subshell distribution, e.g. "1s2 2s2 2p4". */
export function subshellText(detail: ElementDetail): string {
  return Object.entries(detail.subshells)
    .map(([orbital, count]) => `${orbital}${count}`)
    .join(' ');
}

/** The element detail / electron-configuration exploration panel. */
export function ElementDetails({ detail }: { detail: ElementDetail }) {
  const subshells = subshellText(detail);
  return (
    <section className="card element-detail" data-testid="element-detail">
      <header className="element-identity">
        <ElementSymbolBadge detail={detail} />
        <div>
          <h2 data-testid="element-name">{detail.name}</h2>
          <p className="muted">
            {detail.symbol} · atomic number {detail.atomic_number} · period{' '}
            {detail.period} · group {detail.group} · {detail.block}-block
          </p>
        </div>
      </header>

      <div className="element-config">
        <h3>Electron configuration</h3>
        <p className="config-line" data-testid="element-config">
          <ConfigString value={detail.config_full} />
        </p>
        <p className="config-line muted">
          <ConfigString value={detail.config_shorthand} />{' '}
          <span className="help">(noble-gas shorthand, core = {detail.noble_gas})</span>
        </p>
      </div>

      <div className="element-orbitals">
        <h3>Orbital diagram</h3>
        <figure
          className="orbital-figure"
          aria-label={`Orbital diagram: ${subshells}`}
        >
          <div className="orbital-row" data-testid="orbital-diagram">
            {detail.orbitals.map((occ) => (
              <div key={occ.orbital} className="orbital-group">
                <span className="orbital-label">
                  {occ.orbital}
                  <sup>{occ.electrons}</sup>
                </span>
                <div className="orbital-boxes">
                  {orbitalBoxes(occ).map((spin, i) => (
                    <span key={i} className={`orbital-box${spin ? ' filled' : ''}`}>
                      {spin === 'up' ? '↑' : spin === 'down' ? '↓' : ''}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <figcaption className="help muted">
            {subshells}
          </figcaption>
        </figure>
      </div>

      <div className="element-counts">
        <h3>Electron counts</h3>
        <dl className="props" data-testid="element-counts">
          <div className="prop">
            <dt>Valence electrons</dt>
            <dd data-testid="element-valence">{detail.valence_electrons}</dd>
          </div>
          <div className="prop">
            <dt>Core electrons</dt>
            <dd data-testid="element-core">{detail.core_electrons}</dd>
          </div>
          <div className="prop">
            <dt>Unpaired electrons</dt>
            <dd data-testid="element-unpaired">{detail.unpaired_electrons}</dd>
          </div>
        </dl>
      </div>

      <div className="element-shells">
        <h3>Shell distribution</h3>
        <ul className="shell-list" data-testid="element-shells">
          {Object.entries(detail.shells).map(([shell, count]) => (
            <li key={shell}>
              <span className="shell-name">n={shell}</span>
              <span className="shell-count">{count} e⁻</span>
            </li>
          ))}
        </ul>
        <p className="help muted">Electrons per principal shell (not an orbital model).</p>
      </div>

      <details className="element-explanation">
        <summary>What does this configuration mean?</summary>
        <p className="explanation-text" data-testid="element-explanation">
          {detail.explanation}
        </p>
      </details>
    </section>
  );
}

function ElementSymbolBadge({ detail }: { detail: ElementDetail }) {
  return (
    <div className={`element-symbol-box block-${detail.block}`}>
      <span className="element-z">{detail.atomic_number}</span>
      <span className="element-symbol">{detail.symbol}</span>
      <span className="element-mass">{detail.atomic_mass.toFixed(3)}</span>
    </div>
  );
}
