import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    modQueue: vi.fn(),
    modPlayerHistory: vi.fn(),
    modClaim: vi.fn(),
    modInappropriate: vi.fn(),
    modVerdict: vi.fn(),
    modTeams: vi.fn(),
    modResolveFlag: vi.fn(),
  },
  subscribeDeltas: vi.fn(() => () => {}),
}));

vi.mock('../api', () => ({ api: mocks.api }));
vi.mock('../store', () => ({ subscribeDeltas: mocks.subscribeDeltas }));

import { ModConsoleScreen, nextToReview } from './ModConsole';
import { ago } from './mod/ago';
import { QueueList } from './mod/QueueList';

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

// ADR 0029: the console's desktop behaviour.
const make = (id, name, extra = {}) => ({
  ...item,
  id,
  evidence: { id: `ev-${id}`, photo_url: `/api/mod/evidence/ev-${id}/photo` },
  player: { id: `p-${id}`, display_name: name },
  riddle: { sort_order: 1, text: `Riddle for ${name}` },
  ...extra,
});

describe('choosing the next submission', () => {
  const me = 'mod-me';
  // Claimed a moment ago: someone viewing now.
  const other = { id: 'mod-other', label: 'Oracle', claimed_at: Date.now() / 1000 - 30 };

  it('takes the oldest item that no other moderator is viewing', () => {
    const queue = [
      make('a', 'Robin'),
      make('b', 'Toad', { claimed_by: other }),
      make('c', 'Selina'),
    ];
    expect(nextToReview(queue, 'a', me).id).toBe('c');
  });

  it('keeps an item this moderator already claimed', () => {
    const queue = [make('b', 'Toad', { claimed_by: { id: me, label: 'Me' } })];
    expect(nextToReview(queue, 'a', me).id).toBe('b');
  });

  it('returns nothing when every remaining item is someone else\'s', () => {
    expect(nextToReview([make('b', 'Toad', { claimed_by: other })], 'a', me)).toBeNull();
  });

  it('frees an item whose claim was left behind (ADR 0038)', () => {
    const left = { id: 'mod-other', label: 'Oracle', claimed_at: Date.now() / 1000 - 11 * 60 };
    expect(nextToReview([make('b', 'Toad', { claimed_by: left })], 'a', me).id).toBe('b');
  });
});

describe('queue claim labels (ADR 0038)', () => {
  const now = Date.now() / 1000;
  const rows = [
    make('a', 'Robin', { claimed_by: { id: 'mod-me', label: 'Drew', claimed_at: now - 15 * 3600 } }),
    make('b', 'Toad', { claimed_by: { id: 'mod-other', label: 'Oracle', claimed_at: now - 60 } }),
    make('c', 'Selina', { claimed_by: { id: 'mod-other', label: 'Oracle', claimed_at: now - 3 * 3600 } }),
  ];

  it('tells your own claims, a colleague viewing now, and a claim left behind apart', () => {
    render(<QueueList queue={rows} openId={null} onOpen={vi.fn()} moderatorId="mod-me" />);
    expect(screen.getByRole('button', { name: /Robin/ }).textContent).toContain('OPENED BY YOU');
    expect(screen.getByRole('button', { name: /Toad/ }).textContent).toContain('ORACLE IS VIEWING');
    expect(screen.getByRole('button', { name: /Selina/ }).textContent).toContain('ORACLE OPENED 3 H AGO');
  });

  it('counts in hours and days once minutes stop reading well', () => {
    expect(ago(now - 20, now)).toBe('just now');
    expect(ago(now - 45 * 60, now)).toBe('45 min ago');
    expect(ago(now - 745 * 60, now)).toBe('12 h ago');
    expect(ago(now - 3 * 86400, now)).toBe('3 d ago');
  });
});

describe('moderator console layout and flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.api.modPlayerHistory.mockResolvedValue({ submissions: [], strikes: [] });
    mocks.api.modClaim.mockResolvedValue({ ok: true });
    mocks.api.modVerdict.mockResolvedValue({ ok: true });
    mocks.api.modTeams.mockResolvedValue({ teams: [] });
    mocks.api.modResolveFlag.mockResolvedValue({ ok: true });
  });

  it('opens the next free submission after a verdict', async () => {
    const robin = make('a', 'Robin');
    const toad = make('b', 'Toad', { claimed_by: { id: 'mod-other', label: 'Oracle' } });
    const selina = make('c', 'Selina');
    mocks.api.modQueue.mockResolvedValue([robin, toad, selina]);
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: /Robin/ }));
    expect(await screen.findByText('Riddle for Robin')).toBeTruthy();

    mocks.api.modQueue.mockResolvedValue([toad, selina]);
    fireEvent.click(screen.getByRole('button', { name: /Riddle Solved/ }));

    expect(await screen.findByText('Riddle for Selina')).toBeTruthy();
    expect(mocks.api.modVerdict).toHaveBeenCalledWith('a', 'verified', '');
    expect(mocks.api.modClaim).toHaveBeenLastCalledWith('c');
    expect(screen.queryByText('Riddle for Toad')).toBeNull();
  });

  it('opens the next free submission after an inappropriate removal', async () => {
    const robin = make('a', 'Robin');
    const toad = make('b', 'Toad', { claimed_by: { id: 'mod-other', label: 'Oracle' } });
    const selina = make('c', 'Selina');
    mocks.api.modQueue.mockResolvedValue([robin, toad, selina]);
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: /Robin/ }));
    await screen.findByText('Riddle for Robin');

    mocks.api.modQueue.mockResolvedValue([toad, selina]);
    fireEvent.click(screen.getByRole('button', { name: /Flag Inappropriate/ }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm: remove photo/ }));

    expect(await screen.findByText('Riddle for Selina')).toBeTruthy();
    expect(mocks.api.modInappropriate).toHaveBeenCalledWith('a', '', 15);
    expect(mocks.api.modClaim).toHaveBeenLastCalledWith('c');
    expect(screen.queryByText('Riddle for Toad')).toBeNull();
  });

  it('shows the empty state when nothing is left to review', async () => {
    mocks.api.modQueue.mockResolvedValue([make('a', 'Robin')]);
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: /Robin/ }));
    await screen.findByText('Riddle for Robin');

    mocks.api.modQueue.mockResolvedValue([]);
    fireEvent.click(screen.getByRole('button', { name: 'Obscured' }));

    expect(await screen.findByText('Nothing to review right now.')).toBeTruthy();
    expect(screen.queryByText('Riddle for Robin')).toBeNull();
  });

  it('shows a shared photo beside the one it matched, labelled with both teams', async () => {
    const flagged = make('a', 'Toad', {
      flag: {
        distance: 0,
        other_evidence_id: 'ev-z',
        other_photo_url: '/api/mod/evidence/ev-z/photo',
        other_team_label: 'Robin',
      },
    });
    mocks.api.modQueue.mockResolvedValue([flagged]);
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: /Toad/ }));

    const submitted = await screen.findByAltText('This submission — Toad');
    const matched = screen.getByAltText('Matched — Robin · distance 0');
    expect(submitted.getAttribute('src')).toBe('/api/mod/evidence/ev-a/photo');
    expect(matched.getAttribute('src')).toBe('/api/mod/evidence/ev-z/photo');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm duplicate' }));
    await waitFor(() =>
      expect(mocks.api.modResolveFlag).toHaveBeenCalledWith('ev-a', 'confirmed'),
    );
  });

  it('opens a photo full-size and closes it with Escape or the backdrop', async () => {
    mocks.api.modQueue.mockResolvedValue([make('a', 'Robin')]);
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    fireEvent.click(await screen.findByRole('button', { name: /Robin/ }));

    fireEvent.click(await screen.findByRole('button', { name: 'Enlarge the submitted photo' }));
    expect(screen.getByRole('dialog')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Enlarge the submitted photo' }));
    const dialog = screen.getByRole('dialog');
    // A click on the photo itself keeps it open; the backdrop closes it.
    fireEvent.click(dialog.querySelector('img'));
    expect(screen.queryByRole('dialog')).toBeTruthy();
    fireEvent.click(dialog);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('switches the main area to the team rosters and back', async () => {
    mocks.api.modQueue.mockResolvedValue([make('a', 'Robin')]);
    mocks.api.modTeams.mockResolvedValue({
      teams: [{ id: 't1', name: null, size_limit: 1, open_invites: 0,
                members: [{ id: 'p-a', display_name: 'Robin', last_seen_at: 0 }] }],
    });
    render(<ModConsoleScreen copy={copy} moderatorId="mod-me" />);
    await screen.findByRole('button', { name: /Robin/ });

    const teamsButton = screen.getByRole('button', { name: 'Teams' });
    fireEvent.click(teamsButton);
    expect(teamsButton.getAttribute('aria-pressed')).toBe('true');
    expect(await screen.findByRole('region', { name: 'Team rosters' })).toBeTruthy();
    expect(mocks.api.modTeams).toHaveBeenCalledTimes(1);

    // Opening a queue item returns to the review.
    fireEvent.click(screen.getByRole('button', { name: /Robin/ }));
    expect(await screen.findByText('Riddle for Robin')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Team rosters' })).toBeNull();
  });
});
