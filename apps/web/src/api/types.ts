/**
 * Types that mirror the Chemora backend API contracts (see M20):
 *   POST /api/v1/auth/google   → 200 SessionResponse | 401 generic error
 *   GET  /api/v1/auth/me       → 200 CurrentUser     | 401
 *   POST /api/v1/auth/logout   → 204
 *
 * These are derived from the backend's pydantic response models. The client
 * never invents its own user identity — these shapes are what the backend
 * returns, and the backend remains authoritative.
 */

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface SessionResponse {
  user: CurrentUser;
  session_id: string;
}

export interface ErrorResponse {
  detail: string;
}

// ── Chemistry Explorer (M22) ─────────────────────────────────────────────
// Shapes mirror the backend Pydantic models for /api/v1/chemistry/explore.

/** Elemental identity — correct for every input type. */
export interface MoleculeIdentity {
  formula: string;
  exact_mass: number;
  average_mass: number;
  heavy_atom_count: number;
  atom_count: number;
}

/**
 * Structure representation. Only present for structure-bearing inputs
 * (SMILES / InChI / resolved names) — a bare molecular formula does not
 * encode connectivity, so the backend reports `structure_available: false`.
 */
export interface MoleculeStructure {
  canonical_smiles: string;
  formula: string;
  atom_symbols: string[];
  bonds: number[][];
  svg: string;
}

/** Bond-derived descriptors computed by ChemEngine. */
export interface MoleculeProperties {
  logp: number;
  tpsa: number;
  hba: number;
  hbd: number;
  rotatable_bonds: number;
  ring_count: number;
  fraction_csp3: number;
}

export interface ChemistryExploreResult {
  input: string;
  detected_type: string | null;
  structure_available: boolean;
  identity: MoleculeIdentity;
  structure: MoleculeStructure | null;
  properties: MoleculeProperties | null;
}

// ── Element Explorer (M23) ────────────────────────────────────────────────
// Shapes mirror the backend Pydantic models for /api/v1/elements.

/** Periodic-table metadata for one element (GET /api/v1/elements). */
export interface ElementSummary {
  atomic_number: number;
  symbol: string;
  name: string;
  atomic_mass: number;
  period: number;
  group: number;
  block: string;
  category: string;
}

export interface ElementListResult {
  elements: ElementSummary[];
}

/** One occupied subshell in the engine-computed orbital diagram. */
export interface OrbitalOccupancy {
  orbital: string;
  electrons: number;
  capacity: number;
  subshell: string;
  shell: number;
}

/**
 * Full element exploration (GET /api/v1/elements/{identifier}). All electron
 * data is computed by ChemEngine from first principles — the client never
 * calculates configurations itself.
 */
export interface ElementDetail {
  atomic_number: number;
  symbol: string;
  name: string;
  atomic_mass: number;
  period: number;
  group: number;
  block: string;
  category: string;
  config_full: string;
  config_shorthand: string;
  noble_gas: string;
  valence_electrons: number;
  core_electrons: number;
  unpaired_electrons: number;
  shells: Record<string, number>;
  subshells: Record<string, number>;
  orbitals: OrbitalOccupancy[];
  explanation: string;
}
