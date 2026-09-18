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
  /** Highest-shell electron count — the engine's valence definition. */
  valence_electrons: number;
  core_electrons: number;
  unpaired_electrons: number;
  shells: Record<string, number>;
  subshells: Record<string, number>;
  orbitals: OrbitalOccupancy[];
  explanation: string;
}

// ── Learning Core (M24) ───────────────────────────────────────────────────
// Shapes mirror the backend Pydantic models for /api/v1/learning/*.
//
// Architectural rule: educational *content* lives in the backend, and
// chemistry *values* shown inside lessons are not embedded here either —
// `chemistry_spotlight` sections name an element and the client fetches the
// live ChemEngine-computed detail from the existing element API.

/** Catalog entry (GET /api/v1/learning/lessons). */
export interface LessonSummary {
  id: string;
  slug: string;
  title: string;
  description: string;
  subject: string;
  difficulty: string;
  estimated_minutes: number;
  section_count: number;
  question_count: number;
}

export interface LessonListResult {
  lessons: LessonSummary[];
}

/** A practice question as sent to the client — never includes the answer key. */
export interface QuestionPublic {
  id: string;
  kind: string;
  prompt: string;
  options: string[];
}

/** Section kinds the backend may emit. */
export type SectionKind =
  | 'introduction'
  | 'explanation'
  | 'chemistry_spotlight'
  | 'practice'
  | 'summary';

/**
 * One lesson section. `chemistry_spotlight` sections pair prose with live
 * engine data: `element_symbol` names an element (M23 element API) and
 * `molecule_input` names a molecule (M22 chemistry explore API). The client
 * fetches whichever is set — lesson content never stores chemistry values.
 */
export interface SectionPublic {
  id: string;
  kind: string;
  title: string;
  body: string[];
  element_symbol: string | null;
  molecule_input: string | null;
  questions: QuestionPublic[];
}

/** Full lesson (GET /api/v1/learning/lessons/{slug}). */
export interface LessonDetail {
  id: string;
  slug: string;
  title: string;
  description: string;
  subject: string;
  difficulty: string;
  estimated_minutes: number;
  sections: SectionPublic[];
}

/**
 * Per-user progress (GET .../progress, POST .../complete, POST .../answers).
 * `progress_percent` is derived server-side from completed section counts.
 */
export interface LearningProgress {
  lesson_slug: string;
  completed_sections: string[];
  answers: Record<string, boolean>;
  progress_percent: number;
  completed: boolean;
}

/** Server-side answer validation result (POST .../answers). */
export interface AnswerResult {
  question_id: string;
  correct: boolean;
  explanation: string;
  progress: LearningProgress;
}
