import { fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminRiddles: vi.fn(),
    adminPlayers: vi.fn(),
    adminLogin: vi.fn(),
    adminLogout: vi.fn(),
    adminReadyz: vi.fn(),
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { AdminScreen, AdminVersion } from './Admin';

describe('admin console shell', () => {
  beforeEach(() => {
    mocks.api.adminLogin.mockResolvedValue({ ok: true });
    mocks.api.adminLogout.mockResolvedValue({ ok: true });
    mocks.api.adminReadyz.mockResolvedValue({ release: 'dev', schema_version: 5 });
    mocks.api.adminPlayers.mockResolvedValue([]);
  });

  it('offers both sign-in paths when there is no admin session', async () => {
    mocks.api.adminEvents.mockResolvedValue({ unauthenticated: true });

    render(<AdminScreen />);

    const authentik = await screen.findByText('Sign in with Authentik');
    expect(authentik.getAttribute('href')).toBe(
      '/api/auth/oidc/login?next=%2Fadmin',
    );
    expect(screen.getByLabelText('Username')).toBeTruthy();
    expect(screen.getByLabelText('Password')).toBeTruthy();
    expect(screen.queryByText('Host actions')).toBeNull();
  });

  it('renders the console with navigation when a session exists', async () => {
    mocks.api.adminEvents.mockResolvedValue([
      { id: 'event-1', name: 'Gotham Halloween', status: 'open' },
    ]);

    render(<AdminScreen />);

    expect(await screen.findByText('Gotham Halloween')).toBeTruthy();
    for (const label of ['Events', 'Riddles', 'Host actions']) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy();
    }
    expect(screen.queryByLabelText('Password')).toBeNull();
    // Links to the other two views (TKT-01M391CVK8).
    const views = screen.getByRole('navigation', { name: 'Other views' });
    expect(within(views).getByRole('link', { name: 'Moderator console' }).getAttribute('href')).toBe('/mod');
    expect(within(views).getByRole('link', { name: 'Player view' }).getAttribute('href')).toBe('/');
  });

  it('opens the riddle editor on the Riddles tab', async () => {
    mocks.api.adminEvents.mockResolvedValue([
      { id: 'event-1', name: 'Gotham Halloween', status: 'open' },
    ]);
    mocks.api.adminRiddles.mockResolvedValue([
      { id: 'r1', text: 'I guard the door.', sort_order: 0 },
    ]);

    render(<AdminScreen />);

    fireEvent.click(await screen.findByRole('button', { name: 'Riddles' }));

    expect(await screen.findByText('I guard the door.')).toBeTruthy();
    expect(mocks.api.adminRiddles).toHaveBeenCalledWith('event-1');
  });

  it('opens the host actions panel on the Host actions tab', async () => {
    mocks.api.adminEvents.mockResolvedValue([
      { id: 'event-1', name: 'Gotham Halloween', status: 'open' },
    ]);
    mocks.api.adminPlayers.mockResolvedValue([]);

    render(<AdminScreen />);

    fireEvent.click(await screen.findByRole('button', { name: 'Host actions' }));

    expect(
      await screen.findByText(
        'No players yet. Strikes appear here once a moderator flags a submission.',
      ),
    ).toBeTruthy();
    await waitFor(() => {
      expect(mocks.api.adminPlayers).toHaveBeenCalledWith('event-1');
    });
  });

  it('shows a failed password login instead of hanging', async () => {
    mocks.api.adminEvents.mockResolvedValue({ unauthenticated: true });
    mocks.api.adminLogin.mockResolvedValue({
      error: 'bad_credentials',
      message: 'Wrong username or password.',
      status: 401,
    });

    render(<AdminScreen />);

    fireEvent.input(await screen.findByLabelText('Username'), {
      target: { value: 'admin' },
    });
    fireEvent.input(screen.getByLabelText('Password'), {
      target: { value: 'nope' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Wrong username or password.')).toBeTruthy();
    await waitFor(() => {
      const button = screen.getByRole('button', { name: 'Sign in' });
      expect(button.disabled).toBe(false);
    });
  });

  it('reports a probe failure with a retry rather than the login form', async () => {
    mocks.api.adminEvents.mockResolvedValue({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
    });

    render(<AdminScreen />);

    expect(
      await screen.findByText('Could not reach the server. Check your connection.'),
    ).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });
});

// ADR 0041: the host sees which build runs where, and is told to reload a
// page older than the server.
describe('admin version footer', () => {
  it('shows the web build, server release and schema', async () => {
    mocks.api.adminReadyz.mockResolvedValue({ release: 'abc1234', schema_version: 5 });
    render(<AdminVersion build="abc1234" />);
    expect(screen.getByText('Web abc1234')).toBeTruthy();
    expect(await screen.findByText('Server abc1234')).toBeTruthy();
    expect(screen.getByText('Schema 5')).toBeTruthy();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('warns when the page is an older build than the server', async () => {
    mocks.api.adminReadyz.mockResolvedValue({ release: 'new5678', schema_version: 5 });
    render(<AdminVersion build="old1234" />);
    const warning = await screen.findByRole('status');
    expect(warning.textContent).toContain('older build than the server');
    expect(within(warning).getByRole('button', { name: 'Reload' })).toBeTruthy();
  });

  it('does not warn when the server does not know its release', async () => {
    mocks.api.adminReadyz.mockResolvedValue({ release: 'unknown', schema_version: 5 });
    render(<AdminVersion build="dev" />);
    expect(await screen.findByText('Server unknown')).toBeTruthy();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('keeps the web build when readyz fails', async () => {
    mocks.api.adminReadyz.mockResolvedValue({ error: 'network', message: 'offline' });
    render(<AdminVersion build="abc1234" />);
    await waitFor(() => expect(mocks.api.adminReadyz).toHaveBeenCalled());
    expect(screen.getByText('Web abc1234')).toBeTruthy();
    expect(screen.queryByText(/^Server/)).toBeNull();
  });
});
