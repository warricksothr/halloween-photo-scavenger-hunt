import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminRiddles: vi.fn(),
    adminPlayers: vi.fn(),
    adminLogin: vi.fn(),
    adminLogout: vi.fn(),
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { AdminScreen } from './Admin';

describe('admin console shell', () => {
  beforeEach(() => {
    mocks.api.adminLogin.mockResolvedValue({ ok: true });
    mocks.api.adminLogout.mockResolvedValue({ ok: true });
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
