import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    modQueue: vi.fn(),
    modAudit: vi.fn(),
    modTeams: vi.fn(),
  },
  listeners: new Set(),
}));

vi.mock('../../api', () => ({ api: mocks.api }));
vi.mock('../../store', () => ({
  subscribeDeltas: (fn) => {
    mocks.listeners.add(fn);
    return () => mocks.listeners.delete(fn);
  },
}));

import { ModConsoleScreen } from '../ModConsole';
import { logLine, MODERATION_ACTIONS } from './LogPanel';

const T = 1_760_000_000;
const rows = [
  { id: 1, action: 'player.joined', actor_type: 'player', actor_name: 'Robin',
    about: { player: 'Robin', team: 'Robin' }, details: { device_label: 'iPhone' }, created_at: T },
  { id: 2, action: 'verdict.issued', actor_type: 'moderator', actor_name: 'Oracle',
    about: { player: 'Robin', team: 'Robin', riddle: 2, evidence_id: 'ev-9' },
    details: { verdict: 'too_small', flavor_text: 'Move closer.' }, created_at: T + 60 },
  { id: 3, action: 'strike.issued', actor_type: 'moderator', actor_name: 'Nightwing',
    about: { player: 'Joker', team: 'Arkham', riddle: 1, evidence_id: 'ev-3' },
    details: { level: 1, note: 'not ok', cooldown_until: null }, created_at: T + 120 },
];

describe('log lines (ADR 0044)', () => {
  it('says who did what to whom, in plain words', () => {
    expect(logLine(rows[1])).toEqual({
      text: "Oracle marked Robin's photo for Riddle #2 too small",
      detail: 'Move closer.',
      tone: 'warn',
    });
    expect(logLine(rows[2]).text).toBe('Nightwing gave Joker (Arkham) strike 1');
    expect(logLine(rows[2]).detail).toBe('“not ok”');
    expect(logLine(rows[0]).text).toBe('Robin joined');
    expect(logLine({ action: 'event.closed', actor_name: 'Host', details: { expired_pending: 2 } }))
      .toMatchObject({ text: 'Host closed the round', detail: '2 waiting scans expired' });
    expect(logLine({ action: 'team.member_removed', actor_name: 'Oracle',
                     about: { player: 'Bane', team: 'Venom' }, details: {} }).text)
      .toBe('Oracle removed Bane from Venom');
    // An action the console does not know yet still reads as something.
    expect(logLine({ action: 'future.thing', actor_name: 'Host', details: {} }).text)
      .toBe('Host: future.thing');
  });

  it('keeps moderator decisions in the Moderation filter, not player traffic', () => {
    expect(MODERATION_ACTIONS.has('verdict.issued')).toBe(true);
    expect(MODERATION_ACTIONS.has('strike.issued')).toBe(true);
    expect(MODERATION_ACTIONS.has('player.joined')).toBe(false);
    expect(MODERATION_ACTIONS.has('evidence.uploaded')).toBe(false);
  });
});

describe('the Log view', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listeners.clear();
    mocks.api.modQueue.mockResolvedValue([]);
    mocks.api.modAudit.mockResolvedValue(rows);
  });

  async function openLog() {
    render(<ModConsoleScreen copy={{ verdicts: {} }} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Log' }));
    return screen.findByRole('list', { name: 'Moderation log' });
  }

  it('shows moderation newest first, and everything on request', async () => {
    const list = await openLog();
    const items = within(list).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining('Nightwing gave Joker (Arkham) strike 1'),
      expect.stringContaining("Oracle marked Robin's photo for Riddle #2 too small"),
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Everything' }));
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(within(list).getAllByRole('listitem')[2].textContent).toContain('Robin joined');
  });

  it('opens the photo behind a row in the lightbox', async () => {
    const list = await openLog();
    const [strikeRow] = within(list).getAllByRole('listitem');
    fireEvent.click(within(strikeRow).getByRole('button', { name: 'Photo' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.querySelector('img').getAttribute('src')).toBe('/api/mod/evidence/ev-3/photo');
  });

  it('reads the log again on a live delta while it is shown', async () => {
    await openLog();
    expect(mocks.api.modAudit).toHaveBeenCalledTimes(1);
    mocks.api.modAudit.mockResolvedValue([...rows, {
      id: 4, action: 'event.closed', actor_type: 'admin', actor_name: 'Host',
      about: {}, details: { expired_pending: 0 }, created_at: T + 180,
    }]);
    act(() => mocks.listeners.forEach((fn) => fn('event_status', {})));
    expect(await screen.findByText('Host closed the round')).toBeTruthy();

    // Back on the queue, deltas no longer read the log.
    fireEvent.click(screen.getByRole('button', { name: 'Queue' }));
    const calls = mocks.api.modAudit.mock.calls.length;
    act(() => mocks.listeners.forEach((fn) => fn('submission_new', {})));
    await waitFor(() => expect(mocks.api.modQueue).toHaveBeenCalled());
    expect(mocks.api.modAudit).toHaveBeenCalledTimes(calls);
  });
});
