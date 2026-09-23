import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    modQueue: vi.fn(),
    modPlayerHistory: vi.fn(),
    modClaim: vi.fn(),
    modInappropriate: vi.fn(),
  },
  subscribeDeltas: vi.fn(() => () => {}),
}));

vi.mock('../api', () => ({ api: mocks.api }));
vi.mock('../store', () => ({ subscribeDeltas: mocks.subscribeDeltas }));

import { ModConsoleScreen } from './ModConsole';

const item = {
  id: 'sub-1',
  created_at: Math.floor(Date.now() / 1000),
  evidence: { id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' },
  player: { id: 'p-1', display_name: 'Robin' },
  riddle: { sort_order: 1, text: 'Find the signal' },
  flag: null,
  claimed_by: null,
};

const copy = { verdicts: {} };

async function openItem() {
  render(<ModConsoleScreen modEvent={{ name: 'The Hunt' }} copy={copy} />);
  fireEvent.click(await screen.findByRole('button', { name: /Robin/ }));
  await screen.findByLabelText(/^Note/);
}

describe('moderator conduct controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.api.modQueue.mockResolvedValue([item]);
    mocks.api.modPlayerHistory.mockResolvedValue({ submissions: [], strikes: [] });
    mocks.api.modClaim.mockResolvedValue({ ok: true });
    mocks.api.modInappropriate.mockResolvedValue({ ok: true });
  });

  it('sends the typed note and cooldown with the strike', async () => {
    await openItem();

    fireEvent.input(screen.getByLabelText(/^Note/), { target: { value: 'too spooky' } });
    fireEvent.input(screen.getByLabelText(/Cooldown minutes/), { target: { value: '30' } });

    fireEvent.click(screen.getByRole('button', { name: /Flag Inappropriate/ }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm: remove photo/ }));

    await waitFor(() => {
      expect(mocks.api.modInappropriate).toHaveBeenCalledWith('sub-1', 'too spooky', 30);
    });
  });

  it('rejects an out-of-range cooldown before calling the server', async () => {
    await openItem();

    fireEvent.input(screen.getByLabelText(/Cooldown minutes/), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /Flag Inappropriate/ }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm: remove photo/ }));

    expect(await screen.findByText(/Cooldown must be/)).toBeTruthy();
    expect(mocks.api.modInappropriate).not.toHaveBeenCalled();
  });
});
