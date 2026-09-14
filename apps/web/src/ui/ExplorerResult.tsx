import type {
  ChemistryExploreResult,
  MoleculeIdentity,
  MoleculeProperties,
  MoleculeStructure,
} from '../api/types';

/** Renders the structured chemistry result returned by the backend. */
export function ExplorerResult({ result }: { result: ChemistryExploreResult }) {
  return (
    <div className="result" data-testid="explorer-result">
      <IdentityCard identity={result.identity} detectedType={result.detected_type} />
      {result.structure ? (
        <StructureCard structure={result.structure} />
      ) : (
        <FormulaOnlyNote />
      )}
      {result.properties ? <PropertiesCard properties={result.properties} /> : null}
    </div>
  );
}

function IdentityCard({
  identity,
  detectedType,
}: {
  identity: MoleculeIdentity;
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
      </dl>
    </section>
  );
}

function PropertiesCard({ properties }: { properties: MoleculeProperties }) {
  const rows: Array<[string, string]> = [
    ['LogP (Wildman–Crippen)', properties.logp.toFixed(2)],
    ['TPSA (Å²)', properties.tpsa.toFixed(2)],
    ['H-bond acceptors', String(properties.hba)],
    ['H-bond donors', String(properties.hbd)],
    ['Rotatable bonds', String(properties.rotatable_bonds)],
    ['Rings', String(properties.ring_count)],
    ['Fraction C(sp³)', properties.fraction_csp3.toFixed(2)],
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