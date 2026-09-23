import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminCreateEvent: vi.fn(),
    adminOpenEvent: vi.fn(),
    adminCloseEvent: vi.fn(),
    adminPurgeEvent: vi.fn(),
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { AdminEvents } from './AdminEvents';

const lobby = { id: 'ev-1', name: 'Gotham Halloween', status: 'lobby' };

describe('admin event management', () => {
  beforeEach(() => {
    mocks.api.adminEvents.mockResolvedValue([]);
    mocks.api.adminCreateEvent.mockResolvedValue({});
    mocks.api.adminOpenEvent.mockResolvedValue({});
    mocks.api.adminCloseEvent.mockResolvedValue({});
    mocks.api.adminPurgeEvent.mockResolvedValue({});
  });

  it('shows the join and mod URLs with a QR for each after creating', async () => {
    mocks.api.adminCreateEvent.mockResolvedValue({
      id: 'ev-2',
      name: 'Gotham Halloween',
      status: 'lobby',
      join_code: 'JOIN123',
      mod_code: 'MOD456',
    });

    render(<AdminEvents initialEvents={[lobby]} />);

    fireEvent.click(screen.getByRole('button', { name: 'New event' }));
    fireEvent.input(screen.getByLabelText('Event name'), {
      target: { value: 'Gotham Halloween' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create event' }));

    const origin = window.location.origin;
    expect(await screen.findByText(`${origin}/j/JOIN123`)).toBeTruthy();
    expect(screen.getByText(`${origin}/m/MOD456`)).toBeTruthy();

    const codes = screen.getAllByRole('img');
    expect(codes).toHaveLength(2);
    for (const img of codes) {
      expect(img.getAttribute('src')).toMatch(/^data:image\/svg\+xml/);
    }

    expect(mocks.api.adminCreateEvent).toHaveBeenCalledWith({
      name: 'Gotham Halloween',
      theme: 'arkham',
      leaderboard_visibility: 'live',
      team_size_limit: 1,
    });
  });

  it('drives the lifecycle with the one action each status allows', async () => {
    mocks.api.adminEvents.mockResolvedValue([{ ...lobby, status: 'open' }]);
    mocks.api.adminOpenEvent.mockResolvedValue({});

    render(<AdminEvents initialEvents={[lobby]} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(mocks.api.adminOpenEvent).toHaveBeenCalledWith('ev-1');
    expect(await screen.findByRole('button', { name: 'Close' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Open' })).toBeNull();
  });

  it('surfaces the API message when a transition is refused', async () => {
    mocks.api.adminOpenEvent.mockResolvedValue({
      error: 'riddles_required',
      message: 'Add at least one riddle before opening the round.',
      status: 409,
    });

    render(<AdminEvents initialEvents={[lobby]} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open' }));

    expect(
      await screen.findByText('Add at least one riddle before opening the round.'),
    ).toBeTruthy();
    expect(mocks.api.adminEvents).not.toHaveBeenCalled();
  });

  it('requires the event name typed before purging', async () => {
    mocks.api.adminEvents.mockResolvedValue([]);
    const closed = { ...lobby, status: 'closed' };

    render(<AdminEvents initialEvents={[closed]} />);

    fireEvent.click(screen.getByRole('button', { name: 'Purge' }));
    const confirm = screen.getByLabelText('Type the event name to confirm');
    const purge = screen.getByRole('button', { name: 'Purge event' });
    expect(purge.disabled).toBe(true);

    fireEvent.input(confirm, { target: { value: 'wrong' } });
    expect(purge.disabled).toBe(true);
    expect(mocks.api.adminPurgeEvent).not.toHaveBeenCalled();

    fireEvent.input(confirm, { target: { value: 'Gotham Halloween' } });
    expect(purge.disabled).toBe(false);
    fireEvent.click(purge);

    await waitFor(() => {
      expect(mocks.api.adminPurgeEvent).toHaveBeenCalledWith(
        'ev-1',
        'Gotham Halloween',
      );
    });
    expect(await screen.findByText('No events yet. Create one to get the join and moderator codes.')).toBeTruthy();
  });
});
