// The join screen's rejoin list (ADR 0031): the live games this device
// already joined, one tap each, above the ordinary join form.
import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  join: vi.fn(),
  resumableGames: vi.fn(),
  resume: vi.fn(),
}));

vi.mock('../store', () => ({
  join: mocks.join,
  resumableGames: mocks.resumableGames,
  resume: mocks.resume,
}));

import { JoinScreen } from './Join';

const gotham = {
  event_id: 'ev-1',
  event_name: 'Gotham Halloween',
  display_name: 'Robin',
  status: 'open',
  theme: 'arkham',
};
const blackgate = { ...gotham, event_id: 'ev-2', event_name: 'Blackgate', display_name: 'Bruce' };

describe('rejoining a game from the join screen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
  });

  it('lists each joined game with the codename used there', async () => {
    mocks.resumableGames.mockResolvedValue([gotham, blackgate]);
    render(<JoinScreen />);

    const list = await screen.findByRole('region', { name: 'Open Cases' });
    expect(list.textContent).toContain('Gotham Halloween');
    expect(list.textContent).toContain('Return as Robin');
    expect(list.textContent).toContain('Return as Bruce');
    // The ordinary join form is still there below it.
    expect(screen.getByRole('button', { name: 'Join the Hunt' })).toBeTruthy();
  });

  it('shows no list when this device has joined nothing live', async () => {
    mocks.resumableGames.mockResolvedValue([]);
    render(<JoinScreen />);

    await screen.findByRole('button', { name: 'Join the Hunt' });
    await waitFor(() => expect(mocks.resumableGames).toHaveBeenCalled());
    expect(screen.queryByRole('region', { name: 'Open Cases' })).toBeNull();
  });

  it('rejoins the tapped game', async () => {
    mocks.resumableGames.mockResolvedValue([gotham, blackgate]);
    mocks.resume.mockResolvedValue({ event: { id: 'ev-2' } });
    render(<JoinScreen />);

    fireEvent.click(await screen.findByRole('button', { name: /Blackgate/ }));

    await waitFor(() => expect(mocks.resume).toHaveBeenCalledWith('ev-2'));
    expect(mocks.join).not.toHaveBeenCalled();
  });

  it('explains a refusal and drops that game from the list', async () => {
    mocks.resumableGames.mockResolvedValue([gotham, blackgate]);
    mocks.resume.mockResolvedValue({
      error: 'event_closed',
      message: 'This event has already ended.',
    });
    render(<JoinScreen />);

    fireEvent.click(await screen.findByRole('button', { name: /Gotham Halloween/ }));

    expect(await screen.findByText('This event has already ended.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Gotham Halloween/ })).toBeNull();
    expect(screen.getByRole('button', { name: /Blackgate/ }).disabled).toBe(false);
  });
});
