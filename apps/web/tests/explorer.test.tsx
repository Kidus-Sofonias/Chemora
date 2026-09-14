import { vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';
import { ApiClient } from '../src/api/apiClient';
import { ApiAuthService } from '../src/auth/AuthService';
import {
  fakeUser,
  FakeGoogleProvider,
  installFakeBackend,
  jsonResponse,
  noContentResponse,
  type FakeBackend,
} from './helpers';

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
    bonds: [[0, 1, 1], [1, 2, 1], [0, 3, 1], [0, 4, 1], [0, 5, 1], [1, 6, 1], [1, 7, 1], [2, 8, 1]],
    svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>C</text><text>O</text></svg>',
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
  // Wait until the authenticated shell (with the explorer) is visible.
  await screen.findByRole('button', { name: /Explore/ });
  return { backend, provider };
}

function exploreRequests(backend: FakeBackend) {
  return backend.requests.filter((r) => r.url.endsWith('/chemistry/explore'));
}

describe('Chemistry Explorer (web)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('shows the explorer form for an authenticated user', async () => {
    await setupAppWithAuth();

    expect(screen.getByLabelText(/Molecule, formula, or SMILES/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Explore/ })).toBeInTheDocument();
    expect(screen.queryByTestId('explorer-result')).toBeNull();
  });

  test('explores a SMILES string and renders structure + properties', async () => {
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
    expect(screen.getByTestId('identity-formula')).toHaveTextContent('C2H6O');
    expect(screen.getByTestId('canonical-smiles')).toHaveTextContent('CCO');
    expect(screen.getByTestId('structure-svg')).toBeInTheDocument();
    expect(screen.getByTestId('properties-list')).toBeInTheDocument();
    // Exact vs average mass stay distinct in the UI.
    expect(screen.getByTestId('identity-exact-mass')).toHaveTextContent('46.0419');
    expect(screen.getByTestId('identity-average-mass')).toHaveTextContent('46.0690');
    // Requests carry the input to the backend.
    const reqs = exploreRequests(backend);
    expect(reqs.length).toBe(1);
    expect(reqs[0].body).toEqual({ input: 'CCO' });
    expect(reqs[0].credentials).toBe('include');
  });

  test('shows identity-only result with a note for a molecular formula', async () => {
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
    expect(screen.getByTestId('identity-formula')).toHaveTextContent('H2O');
    expect(screen.getByTestId('formula-only-note')).toBeInTheDocument();
    expect(screen.queryByTestId('properties-list')).toBeNull();
    expect(screen.queryByTestId('structure-svg')).toBeNull();
  });

  test('shows a chemistry error for unrecognizable input', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) {
        return jsonResponse(422, {
          detail: { code: 'unsupported_input', message: 'We could not recognize that input.' },
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'zzzz');
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-error');
    expect(screen.getByRole('alert')).toHaveTextContent('We could not recognize that input.');
    expect(screen.queryByTestId('explorer-result')).toBeNull();
  });

  test('distinguishes a network failure from a chemistry error', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'CCO');
    backend.failNextRequestOnce();
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the Chemora server/);
    expect(screen.queryByTestId('explorer-result')).toBeNull();
  });

  test('shows a server error when the backend fails', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return jsonResponse(500, { detail: 'boom' });
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'CCO');
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    await screen.findByTestId('explorer-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/chemistry service hit a problem/i);
    // No stack traces or internals leak into the UI.
    expect(screen.queryByText(/boom/)).toBeNull();
  });

  test('shows a loading state while the request is in flight', async () => {
    const { backend } = await setupAppWithAuth();
    let resolveExplore: (v: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveExplore = resolve;
    });
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return pending;
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Molecule, formula, or SMILES/i), 'CCO');
    await user.click(screen.getByRole('button', { name: /Explore/ }));

    expect(await screen.findByTestId('explorer-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('explorer-result')).toBeNull();

    resolveExplore!(jsonResponse(200, ethanolResult));
    await screen.findByTestId('explorer-result');
  });

  test('does not re-request the same input (avoids repeated requests)', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/chemistry/explore')) return jsonResponse(200, ethanolResult);
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();
    const input = screen.getByLabelText(/Molecule, formula, or SMILES/i);

    await user.type(input, 'CCO');
    await user.click(screen.getByRole('button', { name: /Explore/ }));
    await screen.findByTestId('explorer-result');

    await user.click(screen.getByRole('button', { name: /Explore/ }));
    await waitFor(() => {
      expect(exploreRequests(backend).length).toBe(1);
    });
  });

  test('sign out still works from the authenticated explorer shell', async () => {
    const { backend } = await setupAppWithAuth();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/auth/logout')) return noContentResponse();
      return jsonResponse(404, { detail: 'not found' });
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /Sign out/ }));

    await screen.findByTestId('google-sign-in-host');
    expect(screen.queryByRole('button', { name: /Explore/ })).toBeNull();
  });

});