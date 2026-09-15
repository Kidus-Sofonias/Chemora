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
  type FakeBackend,
  type Handler,
} from './helpers';

const oxygenDetail = {
  atomic_number: 8,
  symbol: 'O',
  name: 'Oxygen',
  atomic_mass: 15.999,
  period: 2,
  group: 16,
  block: 'p',
  category: 'nonmetal',
  config_full: '1s2 2s2 2p4',
  config_shorthand: '[He] 2s2 2p4',
  noble_gas: 'He',
  valence_electrons: 6,
  core_electrons: 2,
  unpaired_electrons: 2,
  shells: { '1': 2, '2': 6 },
  subshells: { '1s': 2, '2s': 2, '2p': 4 },
  orbitals: [
    { orbital: '1s', electrons: 2, capacity: 2, subshell: 's', shell: 1 },
    { orbital: '2s', electrons: 2, capacity: 2, subshell: 's', shell: 2 },
    { orbital: '2p', electrons: 4, capacity: 6, subshell: 'p', shell: 2 },
  ],
  explanation: 'Electron Configuration of Oxygen (O, Z=8)',
};

const heliumDetail = { ...oxygenDetail, symbol: 'He', name: 'Helium', atomic_number: 2 };

const elementsList = {
  elements: [
    { atomic_number: 1, symbol: 'H', name: 'Hydrogen', atomic_mass: 1.008, period: 1, group: 1, block: 's', category: 'nonmetal' },
    { atomic_number: 2, symbol: 'He', name: 'Helium', atomic_mass: 4.0026, period: 1, group: 18, block: 's', category: 'noble_gas' },
    { atomic_number: 8, symbol: 'O', name: 'Oxygen', atomic_mass: 15.999, period: 2, group: 16, block: 'p', category: 'nonmetal' },
    { atomic_number: 26, symbol: 'Fe', name: 'Iron', atomic_mass: 55.845, period: 4, group: 8, block: 'd', category: 'transition_metal' },
  ],
};

function elementRequests(backend: FakeBackend) {
  return backend.requests.filter((r) => r.url.includes('/elements'));
}

const DEFAULT_HANDLER: Handler = (_m, url) => {
  if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
  if (url.endsWith('/elements')) return jsonResponse(200, elementsList);
  if (url.endsWith('/elements')) return jsonResponse(200, elementsList);
  if (url.endsWith('/elements/O')) return jsonResponse(200, oxygenDetail);
  if (url.endsWith('/elements/He')) return jsonResponse(200, heliumDetail);
  return jsonResponse(404, { detail: 'not found' });
};

/** Navigates to the Elements tab, tolerating a failed table load. */
async function gotoElementsTab() {
  await userEvent.setup().click(screen.getByRole('button', { name: 'Elements' }));
}

function renderApp(backend: FakeBackend) {
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  render(<App service={service} provider={provider} api={api} />);
  return backend;
}

async function setupApp(handler: Handler = DEFAULT_HANDLER) {
  const backend = installFakeBackend();
  const provider = new FakeGoogleProvider();
  const api = new ApiClient('http://test');
  const service = new ApiAuthService(api);
  backend.setHandler(handler);
  render(<App service={service} provider={provider} api={api} />);
  await screen.findByRole('button', { name: /Explore/ });
  await gotoElementsTab();
  await screen.findByTestId('periodic-table');
  return { backend };
}

describe('Element Explorer (web)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('renders the periodic table from the engine dataset', async () => {
    await setupApp();
    expect(screen.getByTestId('element-O')).toHaveAccessibleName('Oxygen, atomic number 8');
    expect(screen.getByTestId('element-Fe')).toBeInTheDocument();
    expect(screen.getByTestId('element-He')).toBeInTheDocument();
  });

  test('selecting an element loads and shows its electron structure', async () => {
    const { backend } = await setupApp();
    await userEvent.setup().click(screen.getByTestId('element-O'));

    await screen.findByTestId('element-detail');
    expect(screen.getByTestId('element-name')).toHaveTextContent('Oxygen');
    expect(screen.getByTestId('element-config')).toHaveTextContent('1s2 2s2 2p4');
    expect(screen.getByTestId('element-valence')).toHaveTextContent('6');
    expect(screen.getByTestId('element-core')).toHaveTextContent('2');
    expect(screen.getByTestId('element-unpaired')).toHaveTextContent('2');
    expect(screen.getByTestId('element-shells')).toHaveTextContent('n=2');
    expect(screen.getByTestId('orbital-diagram')).toBeInTheDocument();
    expect(elementRequests(backend).filter((r) => r.url.endsWith('/elements/O')).length).toBe(1);
  });

  test('re-selecting the same element does not refetch (cached)', async () => {
    const { backend } = await setupApp();
    const user = userEvent.setup();
    await user.click(screen.getByTestId('element-O'));
    await screen.findByTestId('element-detail');

    await user.click(screen.getByTestId('element-He'));
    await screen.findByText('Helium');
    await user.click(screen.getByTestId('element-O'));
    await screen.findByText('Oxygen');
    await waitFor(() => {
      expect(elementRequests(backend).filter((r) => r.url.endsWith('/elements/O')).length).toBe(1);
    });
  });

  test('search by atomic number narrows the table', async () => {
    await setupApp();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Search element/i), '26');
    expect(screen.getByTestId('element-Fe')).toBeInTheDocument();
    expect(screen.queryByTestId('element-O')).toBeNull();
  });

  test('search by name matches case-insensitively', async () => {
    await setupApp();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Search element/i), 'oxygen');
    expect(screen.getByTestId('element-O')).toBeInTheDocument();
    expect(screen.queryByTestId('element-Fe')).toBeNull();
  });

  test('search by symbol matches', async () => {
    await setupApp();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Search element/i), 'Fe');
    expect(screen.getByTestId('element-Fe')).toBeInTheDocument();
    expect(screen.queryByTestId('element-O')).toBeNull();
  });

  test('a search with no match shows a clear message', async () => {
    await setupApp();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Search element/i), 'zzz');
    expect(screen.getByTestId('elements-no-match')).toBeInTheDocument();
  });

  test('an unknown element shows a user-facing error without internals', async () => {
    await setupApp((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/elements')) return jsonResponse(200, elementsList);
      if (url.endsWith('/elements/O')) {
        return jsonResponse(404, {
          detail: { code: 'unknown_element', message: 'Element not found.' },
        });
      }
      return jsonResponse(404, { detail: 'not found' });
    });
    await userEvent.setup().click(screen.getByTestId('element-O'));

    await screen.findByTestId('element-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Element not found/);
  });

  test('a network failure while loading shows a network error', async () => {
    const backend = installFakeBackend();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/elements')) throw new TypeError('Failed to fetch');
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp(backend);
    await screen.findByRole('button', { name: /Explore/ });
    await gotoElementsTab();

    await screen.findByTestId('elements-error');
    expect(screen.getByRole('alert')).toHaveTextContent(/Cannot reach the Chemora server/);
  });

  test('a server failure while loading shows a server error', async () => {
    const backend = installFakeBackend();
    backend.setHandler((_m, url) => {
      if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
      if (url.endsWith('/elements')) return jsonResponse(500, { detail: 'boom' });
      return jsonResponse(404, { detail: 'not found' });
    });
    renderApp(backend);
    await screen.findByRole('button', { name: /Explore/ });
    await gotoElementsTab();

    await screen.findByTestId('elements-error');
    expect(screen.queryByText(/boom/)).toBeNull();
  });
});

