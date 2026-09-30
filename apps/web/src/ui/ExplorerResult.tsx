import type {
  BiomoleculeAnalysis,
  ChemistryExplainResponse,
  ChemistryExploreResult,
  FunctionalGroup,
  MoleculeStructure,
} from '../api/types';
import type { ExplainState } from '../chemistry/useExplorer';

/**
 * The structured chemistry result returned by the backend.
 *
 * When `explain` / `explainState` props are provided (i.e. the caller is the
 * Chemistry Explorer surface, not the Learning page spotlight), an
 * "Explain this molecule" control is rendered for structure-bearing molecules.
 */
export function ExplorerResult({
  result,
  explain,
  explainState,
  learningMode,
  onLearningModeToggle,
}: {
  result: ChemistryExploreResult;
  /** Trigger an explanation (M41). Absent → no explain UI (used by the Learning page). */
  explain?: (input: string) => void;
  explainState?: ExplainState;
  learningMode?: boolean;
  onLearningModeToggle?: () => void;
}) {
  const canExplain = !!explain && !!result.structure;
  return (
    <div className="result" data-testid="explorer-result">
      <IdentityCard identity={result.identity} detectedType={result.detected_type} />
      {result.structure ? (
        <StructureCard structure={result.structure} />
      ) : (
        <FormulaOnlyNote />
      )}
      {result.properties ? <PropertiesCard properties={result.properties} /> : null}
      {result.biomolecule ? (
        <BiomoleculeCard biomolecule={result.biomolecule} />
      ) : null}
      {canExplain ? (
        <>
          <ExplainControl
            explainState={explainState}
            learningMode={learningMode}
            onLearningModeToggle={onLearningModeToggle}
            onExplain={() => explain!(result.input)}
          />
          <ExplainPanel explainState={explainState} />
        </>
      ) : null}
    </div>
  );
}

function IdentityCard({
  identity,
  detectedType,
}: {
  identity: ChemistryExploreResult['identity'];
  detectedType: string | null;
}) {
  return (
    <section className="card" aria-labelledby="identity-title">
      <h2 id="identity-title">Molecular identity</h2>
      <dl className="props">
        <div className="prop">
          <dt>Formula</dt>
          <dd data-testid="identity-formula">{identity.formula}</dd>
        </div>
        <div className="prop">
          <dt>Detected input</dt>
          <dd>{detectedType ?? 'unknown'}</dd>
        </div>
        <div className="prop">
          <dt>Exact mass (monoisotopic)</dt>
          <dd data-testid="identity-exact-mass">{identity.exact_mass.toFixed(4)} g/mol</dd>
        </div>
        <div className="prop">
          <dt>Average mass</dt>
          <dd data-testid="identity-average-mass">{identity.average_mass.toFixed(4)} g/mol</dd>
        </div>
        <div className="prop">
          <dt>Heavy atoms</dt>
          <dd>{identity.heavy_atom_count}</dd>
        </div>
        <div className="prop">
          <dt>Total atoms</dt>
          <dd>{identity.atom_count}</dd>
        </div>
      </dl>
    </section>
  );
}

function StructureCard({ structure }: { structure: MoleculeStructure }) {
  const summary = `${structure.formula}: ${structure.atom_symbols.length} atoms, ${structure.bonds.length} bonds`;
  const groups = structure.functional_groups ?? [];
  return (
    <section className="card" aria-labelledby="structure-title">
      <h2 id="structure-title">Structure</h2>
      <figure className="structure-figure">
        {/* ChemEngine generates this SVG server-side from the parsed graph;
            no user-supplied markup is ever injected. */}
        <div
          className="structure-svg"
          role="img"
          aria-label={`Molecular structure of ${summary}`}
          data-testid="structure-svg"
          dangerouslySetInnerHTML={{ __html: structure.svg }}
        />
        <figcaption className="muted">{summary}</figcaption>
      </figure>
      <dl className="props">
        <div className="prop">
          <dt>Canonical SMILES</dt>
          <dd>
            <code data-testid="canonical-smiles">{structure.canonical_smiles}</code>
          </dd>
        </div>
        <div className="prop">
          <dt>Atoms</dt>
          <dd>{structure.atom_symbols.join(' · ')}</dd>
        </div>
        {groups.length > 0 ? (
          <div className="prop">
            <dt>Functional groups</dt>
            <dd data-testid="functional-groups">
              <ul className="group-list" aria-label="Detected functional groups">
                {groups.map((g) => (
                  <li key={g.name}>
                    <span className="group-badge">{g.name}</span>
                    <span className="muted">({g.categories.join(', ')})</span>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}

function PropertiesCard({ properties }: { properties: ChemistryExploreResult['properties'] }) {
  const props = properties!;
  const rows: Array<[string, string]> = [
    ['LogP (Wildman–Crippen)', props.logp.toFixed(2)],
    ['TPSA (Å²)', props.tpsa.toFixed(2)],
    ['H-bond acceptors', String(props.hba)],
    ['H-bond donors', String(props.hbd)],
    ['Rotatable bonds', String(props.rotatable_bonds)],
    ['Rings', String(props.ring_count)],
    ['Fraction C(sp³)', props.fraction_csp3.toFixed(2)],
  ];
  return (
    <section className="card" aria-labelledby="properties-title">
      <h2 id="properties-title">Properties</h2>
      <dl className="props" data-testid="properties-list">
        {rows.map(([label, val]) => (
          <div className="prop" key={label}>
            <dt>{label}</dt>
            <dd>{val}</dd>
          </div>
        ))}
      </dl>
      <p className="help muted">
        Descriptors are computed by ChemEngine and are estimates based on the
        molecular graph.
      </p>
    </section>
  );
}

function BiomoleculeCard({ biomolecule }: { biomolecule: BiomoleculeAnalysis }) {
  const bondCount = biomolecule.peptide_bonds.length;
  return (
    <section className="card" aria-labelledby="biomolecule-title">
      <h2 id="biomolecule-title">Biomolecular analysis (M40)</h2>
      <dl className="props">
        <div className="prop">
          <dt>Biomolecule class</dt>
          <dd data-testid="biomolecule-class">{biomolecule.biomolecule_class}</dd>
        </div>
        <div className="prop">
          <dt>Sequence</dt>
          <dd data-testid="biomolecule-sequence">
            {biomolecule.sequence || <span className="muted">—</span>}
          </dd>
        </div>
        <div className="prop">
          <dt>Residues</dt>
          <dd data-testid="biomolecule-residue-count">{biomolecule.residue_count}</dd>
        </div>
        <div className="prop">
          <dt>Peptide bonds</dt>
          <dd data-testid="biomolecule-peptide-bonds">{bondCount}</dd>
        </div>
        <div className="prop">
          <dt>Chain length</dt>
          <dd data-testid="biomolecule-chain-length">{biomolecule.chain_length}</dd>
        </div>
      </dl>
      <p className="help muted">
        Classified and sequenced by ChemEngine's biomolecular analysis. The
        residues, sequence, and peptide-bond count are read directly from the
        molecular graph.
      </p>
    </section>
  );
}

function FormulaOnlyNote() {
  return (
    <section className="card note-card" aria-labelledby="formula-note-title">
      <h2 id="formula-note-title">Structure not available</h2>
      <p data-testid="formula-only-note">
        A molecular formula describes composition, but not how the atoms are
        connected. Enter a SMILES string, an InChI, or a common name to see the
        molecular structure and derived properties.
      </p>
    </section>
  );
}

// ── M41: Explain control + result rendering ────────────────────────────────

function ExplainControl({
  explainState,
  learningMode,
  onLearningModeToggle,
  onExplain,
}: {
  explainState?: ExplainState;
  learningMode?: boolean;
  onLearningModeToggle?: () => void;
  onExplain: () => void;
}) {
  const loading = explainState?.kind === 'loading';
  return (
    <section className="card explain-control" aria-label="Explain this molecule">
      <div className="explain-control-head">
        <h2 id="explain-title">Explain this molecule</h2>
        <button
          type="button"
          className={`switch ${learningMode ? 'on' : 'off'}`}
          role="switch"
          aria-checked={learningMode}
          aria-label={
            learningMode
              ? 'Learning mode is on (student-friendly explanations)'
              : 'Learning mode is off (technical explanations)'
          }
          id="learning-mode-toggle"
          data-testid="learning-mode-toggle"
          onClick={onLearningModeToggle}
        >
          <span className="switch-thumb" aria-hidden="true" />
        </button>
        <label className="muted" htmlFor="learning-mode-toggle">
          Learning mode
        </label>
      </div>
      <p className="help muted">
        {learningMode
          ? 'Explanations use plain language and scaffolding.'
          : 'Explanations use technical language.'}
      </p>
      <button
        type="button"
        className="button primary"
        data-testid="explain-button"
        disabled={loading}
        onClick={onExplain}
      >
        {loading ? 'Explaining…' : 'Explain this molecule'}
      </button>
    </section>
  );
}

function ExplainPanel({ explainState }: { explainState?: ExplainState }) {
  if (!explainState) {
    return null;
  }
  if (explainState.kind === 'idle') {
    return null;
  }
  if (explainState.kind === 'loading') {
    return (
      <p
        className="status"
        role="status"
        data-testid="explain-loading"
        aria-live="polite"
      >
        Explaining {explainState.input}…
      </p>
    );
  }
  if (explainState.kind === 'success') {
    return <ExplainResult answer={explainState.answer} />;
  }
  // error
  return (
    <div
      className="card error-card"
      role="alert"
      data-testid="explain-error"
    >
      <h3>Could not explain this molecule</h3>
      <p>{explainState.message}</p>
    </div>
  );
}

function ExplainResult({ answer }: { answer: ChemistryExplainResponse }) {
  const facts = answer.facts;
  const groups = facts.functional_groups?.map((g: FunctionalGroup) => g.name).join(', ') || 'none detected';
  const keyFacts = [
    `${facts.formula} · ${facts.atom_count} atoms · ${facts.heavy_atom_count} heavy atoms`,
    `Exact mass ${facts.exact_mass.toFixed(4)} g/mol`,
    `Functional groups: ${groups}`,
    `LogP ${facts.properties.logp.toFixed(2)} · TPSA ${facts.properties.tpsa.toFixed(2)} Å²`,
  ];
  return (
    <section className="card explain-result" data-testid="explain-result">
      <h2 id="explain-result-title">AI explanation</h2>
      <dl className="props" aria-label="Engine-computed facts (shown verbatim)">
        {keyFacts.map((fact) => (
          <div className="prop" key={fact}>
            <dd data-testid="explain-fact">{fact}</dd>
          </div>
        ))}
      </dl>
      <blockquote className="explanation-text" data-testid="explanation-text">
        {answer.explanation}
      </blockquote>
      <p className="help muted">
        The facts above are computed by ChemEngine; the explanation is the AI
        tutor's reasoning over those facts.
      </p>
    </section>
  );
}
