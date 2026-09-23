import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminPlayers: vi.fn(),
    adminReverseStrike: vi.fn(),
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { AdminHost } from './AdminHost';

const event = { id: 'ev-1', name: 'Gotham Halloween', status: 'open' };

function player(overrides = {}) {
  return {
    id: 'p1',
    display_name: 'Batman',
    team_id: 't1',
    team_name: null,
    restriction: { level: 1, cooldown_until: null, pending_notice: true },
    strikes: [
      {
        id: 's1',
        level: 1,
        note: 'not a party photo',
        cooldown_until: null,
        created_at: 1700000000,
        reversed_at: null,
      },
    ],
    ...overrides,
  };
}

describe('admin host actions', () => {
  beforeEach(() => {
    mocks.api.adminEvents.mockResolvedValue([event]);
    mocks.api.adminPlayers.mockResolvedValue([player()]);
    mocks.api.adminReverseStrike.mockResolvedValue({ ok: true, id: 's1' });
  });

  it('shows the selected player\'s restriction and strike history', async () => {
    render(<AdminHost />);

    expect(await screen.findByRole('option', { name: 'Batman — 1 strike' })).toBeTruthy();
    expect(mocks.api.adminPlayers).toHaveBeenCalledWith('ev-1');
    expect(screen.getByText(/Restriction:/).textContent).toContain('Warned');
    expect(screen.getByText(/not a party photo/)).toBeTruthy();
  });

  it('confirms before reversing and reflects the result', async () => {
    const reversed = player({
      restriction: { level: 0, cooldown_until: null, pending_notice: false },
      strikes: [
        {
          id: 's1',
          level: 1,
          note: 'not a party photo',
          cooldown_until: null,
          created_at: 1700000000,
          reversed_at: 1700000600,
        },
      ],
    });
    mocks.api.adminPlayers
      .mockResolvedValueOnce([player()])
      .mockResolvedValue([reversed]);

    render(<AdminHost />);

    fireEvent.click(await screen.findByRole('button', { name: 'Reverse' }));
    expect(mocks.api.adminReverseStrike).not.toHaveBeenCalled();

    fireEvent.input(screen.getByLabelText('Reversal reason for strike 1'), {
      target: { value: '  mis-tap  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reversal' }));

    await waitFor(() => {
      expect(mocks.api.adminReverseStrike).toHaveBeenCalledWith('s1', 'mis-tap');
    });
    expect(await screen.findByText(/Reversed/)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/Restriction:/).textContent).toContain('Clean');
    });
    expect(screen.queryByRole('button', { name: 'Reverse' })).toBeNull();
  });

  it('keeps the history and surfaces the server error when a reversal fails', async () => {
    mocks.api.adminReverseStrike.mockResolvedValue({
      error: 'already_reversed',
      message: 'That strike was already reversed.',
      status: 409,
    });

    render(<AdminHost />);

    fireEvent.click(await screen.findByRole('button', { name: 'Reverse' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reversal' }));

    expect(
      await screen.findByText('That strike was already reversed.'),
    ).toBeTruthy();
    expect(screen.getByText(/not a party photo/)).toBeTruthy();
  });

  it('does not fire a second reversal while one is in flight', async () => {
    let finish;
    mocks.api.adminReverseStrike.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );

    render(<AdminHost />);

    fireEvent.click(await screen.findByRole('button', { name: 'Reverse' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reversal' }));
    expect(mocks.api.adminReverseStrike).toHaveBeenCalledTimes(1);

    finish({ ok: true });
    await waitFor(() => {
      expect(mocks.api.adminPlayers).toHaveBeenCalledTimes(2);
    });
  });

  it('says a player has no strikes rather than showing an empty list', async () => {
    mocks.api.adminPlayers.mockResolvedValue([
      player({
        restriction: { level: 0, cooldown_until: null, pending_notice: false },
        strikes: [],
      }),
    ]);

    render(<AdminHost />);

    expect(
      await screen.findByText('No strikes on record for Batman.'),
    ).toBeTruthy();
  });

  it('clears a failed load when another event loads', async () => {
    mocks.api.adminEvents.mockResolvedValue([
      event,
      { id: 'ev-2', name: 'Second Night', status: 'open' },
    ]);
    mocks.api.adminPlayers.mockImplementation((id) =>
      id === 'ev-1'
        ? Promise.resolve({
            error: 'internal_error',
            message: 'Could not load players.',
            status: 500,
          })
        : Promise.resolve([
            player({ display_name: 'Robin', strikes: [], restriction: {
              level: 0,
              cooldown_until: null,
              pending_notice: false,
            } }),
          ]),
    );

    render(<AdminHost />);

    expect(await screen.findByText('Could not load players.')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Event'), {
      target: { value: 'ev-2' },
    });

    expect(await screen.findByRole('option', { name: 'Robin' })).toBeTruthy();
    expect(screen.queryByText('Could not load players.')).toBeNull();
  });

  it('points at the Events tab when there is no event yet', async () => {
    mocks.api.adminEvents.mockResolvedValue([]);

    render(<AdminHost />);

    expect(
      await screen.findByText(
        'Create an event on the Events tab first; strikes belong to a player in an event.',
      ),
    ).toBeTruthy();
    expect(mocks.api.adminPlayers).not.toHaveBeenCalled();
  });
});
