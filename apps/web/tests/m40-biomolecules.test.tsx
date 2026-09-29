/**
 * M40 biomolecular analysis web tests.
 *
 * Verifies that the Explorer renders the biomolecule card when the backend
 * returns biomolecular analysis data, and omits it for non-biomolecular
 * inputs.
 */
import { vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';
import { ApiClient } from '../src/api/apiClient';
import { ApiAuthService } from '../src/auth/AuthService';
import {
  fakeUser,
  FakeGoogleProvider,
  installFakeBackend,
  jsonResponse,
} from './helpers';

const peptideResult = {
  input: 'NC(C)C(=O)NC(C(C)C)C(=O)N1C(C(=O)O)CCC1',
  detected_type: 'smiles',
  structure_available: true,
  identity: {
    formula: 'C7H12N2O3',
    exact_mass: 172.084466,
    average_mass: 172.181,
    heavy_atom_count: 12,
    atom_count: 22,
  },
  structure: {
    canonical_smiles: 'NC(C)C(O)NC(C(C)C)Cc1ccccc1',
    formula: 'C7H12N2O3',
    atom_symbols: ['N', 'C', 'C', 'C', 'N', 'C'],
    bonds: [[0, 1, 1]],
    svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
  },
  properties: {
    logp: -1.0,
    tpsa: 90.0,
    hba: 4,
    hbd: 3,
    rotatable_bonds: 6,
    ring_count: 1,
    fraction_csp3: 0.6667,
  },
  biomolecule: {
    schema: 'chemengine-biomolecule-analysis/v1',
    catalogue_version: '1.0.0',
    residue_count: 3,
    residues: [
      { type: 'Ala', atom_indices: [0, 1, 2, 3], position: 0, one_letter_code: 'A' },
      { type: 'Val', atom_indices: [4, 5, 6, 7], position: 1, one_letter_code: 'V' },
      { type: 'Pro', atom_indices: [8, 9, 10, 11], position: 2, one_letter_code: 'P' },
    ],
    sequence: 'AVP',
    peptide_bonds: [[3, 4, 5], [10, 11, 12]],
    biomolecule_class: 'amino_acid',
    chain_length: 22,
    molecular_formula: 'C7H12N2O3',
    canonical_smiles: 'NC(C)C(=O)NC(C(C)C)C(=O)N1C(C(=O)O)CCC1',
  },
};

const ethanolResult = {
  input: 'CCO',
  detected_type: 'smiles',
  structure_available: true,
  identity: {
    formula: 'C2H6O',
    exact_mass: 46.041865,
    average_mass: 46.069,
    heavy_atom_count: 3,
    atom_count: 9,
  },
  structure: {
    canonical_smiles: 'CCO',
    formula: 'C2H6O',
    atom_symbols: ['C', 'C', 'O', 'H', 'H', 'H', 'H', 'H', 'H'],
    bonds: [[0, 1, 1], [1, 2, 1]],
    svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
  },
  properties: {
    logp: 0.0823,
    tpsa: 20.23,
    hba: 1,
    hbd: 1,
    rotatable_bonds: 0,
    ring_count: 0,
    fraction_csp3: 1,
  },
  // Non-biomolecular: class "none", no residues.
  biomolecule: {
    schema: 'chemengine-biomolecule-analysis/v1',
    catalogue_version: '1.0.0',
    residue_count: 0,
    residues: [],
    sequence: '',
    peptide_bonds: [],
    biomolecule_class: 'none',
    chain_length: 9,
    molecular_formula: 'C2H6O',
    canonical_smiles: 'CCO',
  },
};

const waterResult = {
  input: 'H2O',
  detected_type: 'formula',
  structure_available: false,
  identity: {
    formula: 'H2O',
    exact_mass: 18.010565,
    average_mass: 18.015,
    heavy_atom_count: 1,
    atom_count: 3,
  },
  structure: null,
  properties: null,
  // Non-biomolecular: no biomolecule field.
};

async function setupAppWithAuth() {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler((_m, url) => {
    if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
    return jsonResponse(404, { detail: 'not found' });
  });
  render(<App service={service} provider={provider} api={api} />);
  await screen.findByRole('button', { name: /Explore/ });
  return { backend, provider };
}

describe('M40: biomolecular analysis card', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('renders the biomolecule card for a peptide SMILES', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return jsonResponse(200, peptideResult);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Molecule, formula, or SMILES/i),
      peptideResult.input,
    );
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-result');
    expect(screen.getByText('Biomolecular analysis (M40)')).toBeInTheDocument();
    expect(screen.getByTestId('biomolecule-class')).toHaveTextContent('amino_acid');
    expect(screen.getByTestId('biomolecule-sequence')).toHaveTextContent('AVP');
    expect(screen.getByTestId('biomolecule-residue-count')).toHaveTextContent('3');
    expect(screen.getByTestId('biomolecule-peptide-bonds')).toHaveTextContent('2');
    expect(screen.getByTestId('biomolecule-chain-length')).toHaveTextContent('22');
  });

  test('shows the card (class none) for non-biomolecular ethanol', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return jsonResponse(200, ethanolResult);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'CCO');
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-result');
    expect(screen.getByTestId('biomolecule-class')).toHaveTextContent('none');
    expect(screen.getByTestId('biomolecule-sequence')).toHaveTextContent('—');
    expect(screen.getByTestId('biomolecule-residue-count')).toHaveTextContent('0');
    expect(screen.getByTestId('biomolecule-peptide-bonds')).toHaveTextContent('0');
  });

  test('omits the biomolecule card when the backend returns null', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return jsonResponse(200, waterResult);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'H2O');
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-result');
    expect(screen.queryByTestId('biomolecule-class')).toBeNull();
    expect(screen.queryByText('Biomolecular analysis (M40)')).toBeNull();
  });
});

