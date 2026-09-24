import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminCreateEvent: vi.fn(),
    adminOpenEvent: vi.fn(),
    adminCloseEvent: vi.fn(),
    adminPurgeEvent: vi.fn(),
    adminEventCodes: vi.fn(),
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
    mocks.api.adminEventCodes.mockResolvedValue({
      join_code: 'JOIN123',
      mod_code: 'MOD456',
    });
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

    // Inline SVG, not an <img>: the production CSP (img-src 'self')
    // blocks a data: URI image, so the QR never loads one (ADR 0026).
    const codes = screen.getAllByRole('img');
    expect(codes).toHaveLength(2);
    for (const qr of codes) {
      expect(qr.tagName.toLowerCase()).toBe('svg');
      expect(qr.querySelector('path').getAttribute('d')).toMatch(/^M\d/);
    }
    expect(document.querySelector('img')).toBeNull();

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

    mocks.api.adminEvents.mockResolvedValue([{ ...lobby, status: 'closed' }]);
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    expect(mocks.api.adminCloseEvent).toHaveBeenCalledWith('ev-1');
    expect(await screen.findByRole('button', { name: 'Purge' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull();
  });

  it('keeps the guard until the refetch lands so a stale second click cannot fire', async () => {
    let release;
    mocks.api.adminEvents.mockResolvedValue([{ ...lobby, status: 'open' }]);

    render(<AdminEvents initialEvents={[lobby]} />);

    mocks.api.adminOpenEvent.mockResolvedValue({});
    const pending = new Promise((resolve) => {
      release = () => resolve([{ ...lobby, status: 'open' }]);
    });
    mocks.api.adminEvents.mockReturnValue(pending);

    fireEvent.click(screen.getByRole('button', { name: 'Open' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Open' }).disabled).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(mocks.api.adminOpenEvent).toHaveBeenCalledTimes(1);

    release();
    expect(await screen.findByRole('button', { name: 'Close' })).toBeTruthy();
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

  it('shows an existing event\'s join link and QR on demand, the mod link only when revealed', async () => {
    render(<AdminEvents initialEvents={[lobby]} />);
    const origin = window.location.origin;
    expect(screen.queryByText(`${origin}/j/JOIN123`)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    // The card's <code>; the print sheet repeats the URL off screen.
    expect(await screen.findByText(`${origin}/j/JOIN123`, { selector: 'code' })).toBeTruthy();
    expect(mocks.api.adminEventCodes).toHaveBeenCalledWith('ev-1');
    expect(screen.getByRole('img', { name: 'Player join link QR code' })).toBeTruthy();
    // Never on a projected screen by accident.
    expect(screen.queryByText(`${origin}/m/MOD456`)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Reveal moderator link' }));
    expect(screen.getByText(`${origin}/m/MOD456`)).toBeTruthy();
    // The host moderates too (ADR 0027): the card opens the queue directly.
    const open = screen.getByRole('link', { name: 'Open moderator console' });
    expect(open.getAttribute('href')).toBe(`${origin}/m/MOD456`);
    expect(open.getAttribute('target')).toBe('_blank');

    fireEvent.click(screen.getByRole('button', { name: 'Hide links' }));
    expect(screen.queryByText(`${origin}/j/JOIN123`)).toBeNull();
    expect(document.querySelector('.admin-print-sheet')).toBeNull();
  });

  it('puts a large join QR print sheet on the body and prints it', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    render(<AdminEvents initialEvents={[lobby]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    await screen.findByRole('button', { name: 'Print' });

    const sheet = document.querySelector('body > .admin-print-sheet');
    expect(sheet).toBeTruthy();
    expect(sheet.textContent).toContain('Gotham Halloween');
    expect(sheet.textContent).toContain(`${window.location.origin}/j/JOIN123`);
    expect(sheet.querySelector('svg.admin-print-qr')).toBeTruthy();
    // The mod link is never on the sheet.
    expect(sheet.textContent).not.toContain('MOD456');

    fireEvent.click(screen.getByRole('button', { name: 'Print' }));
    expect(print).toHaveBeenCalled();
    print.mockRestore();
  });

  it('downloads the join QR as SVG named after the event', async () => {
    const created = [];
    URL.createObjectURL = vi.fn((blob) => {
      created.push(blob);
      return 'blob:qr';
    });
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function () {
        created.push(this.download);
      });

    render(<AdminEvents initialEvents={[lobby]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    fireEvent.click(await screen.findByRole('button', { name: 'SVG' }));

    const [blob, filename] = created;
    expect(filename).toBe('gotham-halloween-join-qr.svg');
    expect(blob.type).toBe('image/svg+xml');
    // jsdom's Blob has no text(); FileReader is the portable read.
    const svg = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsText(blob);
    });
    expect(svg).toMatch(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg"/);
    // Only matrix numbers reach the file, never the link text.
    expect(svg).not.toContain('JOIN123');
    click.mockRestore();
  });

  it('hands the view back when the session dies while fetching codes', async () => {
    const onSessionExpired = vi.fn();
    mocks.api.adminEventCodes.mockResolvedValue({ unauthenticated: true });
    mocks.api.adminEvents.mockResolvedValue({ unauthenticated: true });
    render(<AdminEvents initialEvents={[lobby]} onSessionExpired={onSessionExpired} />);
    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
  });

  it('shows the API message when the codes cannot be read', async () => {
    mocks.api.adminEventCodes.mockResolvedValue({
      error: 'event_not_found',
      message: 'No such event.',
    });
    render(<AdminEvents initialEvents={[lobby]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    expect(await screen.findByText('No such event.')).toBeTruthy();
  });

  it('keeps the latest event\'s links when an earlier codes response lands last', async () => {
    const second = { id: 'ev-2', name: 'Arkham After Dark', status: 'lobby' };
    const pending = {};
    mocks.api.adminEventCodes.mockImplementation(
      (id) => new Promise((resolve) => { pending[id] = resolve; }),
    );
    render(<AdminEvents initialEvents={[lobby, second]} />);
    const [first, next] = screen.getAllByRole('button', { name: 'Links & QR' });
    fireEvent.click(first);
    fireEvent.click(next);

    const origin = window.location.origin;
    pending['ev-2']({ join_code: 'SECOND', mod_code: 'M2' });
    expect(await screen.findByText(`${origin}/j/SECOND`, { selector: 'code' })).toBeTruthy();
    // The stale response for the first event must not take the panel back.
    pending['ev-1']({ join_code: 'FIRST', mod_code: 'M1' });
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText(`${origin}/j/FIRST`, { selector: 'code' })).toBeNull();
    expect(screen.getByText(`${origin}/j/SECOND`, { selector: 'code' })).toBeTruthy();
  });

  it('shows nothing for an event purged while its codes were loading', async () => {
    // The panel and its print sheet render only inside an event row, so a
    // late response for a purged event has nowhere to appear; closeLinks()
    // also drops it, so the codes do not linger in state (Terva r2).
    const closed = { ...lobby, status: 'closed' };
    let resolveCodes;
    mocks.api.adminEventCodes.mockImplementation(
      () => new Promise((resolve) => { resolveCodes = resolve; }),
    );
    mocks.api.adminEvents.mockResolvedValue([]);
    render(<AdminEvents initialEvents={[closed]} />);

    fireEvent.click(screen.getByRole('button', { name: 'Links & QR' }));
    fireEvent.click(screen.getByRole('button', { name: 'Purge' }));
    fireEvent.input(screen.getByLabelText('Type the event name to confirm'), {
      target: { value: closed.name },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Purge event' }));
    await screen.findByText('No events yet. Create one to get the join and moderator codes.');

    resolveCodes({ join_code: 'GONE', mod_code: 'GONE2' });
    await new Promise((r) => setTimeout(r, 0));
    expect(document.body.textContent).not.toContain('GONE');
    expect(document.querySelector('.admin-print-sheet')).toBeNull();
  });
});
