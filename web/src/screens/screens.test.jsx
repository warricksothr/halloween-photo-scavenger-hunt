import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    drawer: vi.fn(),
    noticeAck: vi.fn(),
    inviteInfo: vi.fn(),
    redeemInvite: vi.fn(),
  },
  refresh: vi.fn(),
}));

vi.mock('../api', () => ({ api: mocks.api }));
vi.mock('../store', () => ({ refresh: mocks.refresh }));

import { DrawerScreen } from './Drawer';
import { RiddleDetailScreen } from './RiddleDetail';
import { RiddleListScreen } from './RiddleList';
import { StrikeNoticeScreen } from './StrikeNotice';
import { ConnectionErrorScreen } from './ConnectionError';
import { TeamJoinScreen } from './TeamJoin';

const copy = {
  tiles: { unsolvedGlyph: '?' },
  verdicts: {
    pending: { headline: 'SCANNING', subtext: 'Checking the evidence.' },
  },
  screens: {
    drawer: {
      headline: 'Evidence Drawer',
      capture: 'Take a Photo',
      addLabel: 'Add a photo',
      photoAlt: 'Your evidence photo',
      uploading: 'Uploading',
      loading: 'Loading drawer',
      empty: 'Drawer empty',
      backToRiddle: (n) => `Back to riddle ${n}`,
      forRiddle: (n) => `For riddle ${n}`,
    },
    detail: {
      alreadyScanning: 'Already scanning.',
      back: 'Back',
      emptyDrawer: 'Drawer empty',
      evidenceOption: (position) => `Evidence photo ${position}`,
      inUsePending: (n) => `Scanning riddle ${n}`,
      inUseSolved: (n) => `Solved riddle ${n}`,
      photoTaken: (n) => `Already on riddle ${n}`,
      loading: 'Loading drawer',
      needNudge: 'Need a nudge?',
      noMoreHints: 'That is every hint.',
      pickEvidence: 'Submit evidence',
      submit: 'Submit evidence',
      submitting: 'Submitting',
      takeNew: 'Take a new photo',
    },
    riddles: {
      headline: 'Riddle Board',
      empty: 'No riddles on the board yet.',
      tile: (state, text) =>
        state === 'verified'
          ? `Riddle solved: ${text}`
          : state === 'pending'
            ? `Riddle scanning: ${text}`
            : `Open riddle: ${text}`,
    },
    teamJoin: {
      headline: 'You Have Been Recruited',
      teamLine: (teamName, eventName) =>
        `${teamName} wants you on their team — ${eventName}.`,
      nameLabel: 'Codename',
      join: 'Join the Team',
      expired: 'That invite link is expired.',
      switchHeadline: 'Changing Teams?',
      switchBody: 'Your evidence stays with your current team.',
      stay: 'Stay',
      switchConfirm: 'Switch team',
      full: 'That team is full.',
    },
  },
};

function snapshot({ riddleState = 'unsolved', restrictionLevel = 0, hints = [] } = {}) {
  return {
    riddles: [
      { id: 'riddle-1', state: riddleState, text: 'Find the signal', hints },
    ],
    submissions: [],
    me: { restriction: { level: restrictionLevel } },
  };
}

describe('player screens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    mocks.api.drawer.mockResolvedValue([]);
    mocks.api.noticeAck.mockResolvedValue({ ok: true });
    mocks.refresh.mockResolvedValue(undefined);
  });

  it('does not offer submission while a riddle is being scanned', async () => {
    render(
      <RiddleDetailScreen
        snapshot={snapshot({ riddleState: 'pending' })}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    expect(screen.getByText('SCANNING')).toBeTruthy();
    await waitFor(() => expect(mocks.api.drawer).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Submit evidence' })).toBeNull();
  });

  it('reveals hints one level per press, and none before asking', async () => {
    render(
      <RiddleDetailScreen
        snapshot={snapshot({ hints: ['Higher.', 'Braced or cabled.'] })}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    // Nothing is shown until the player asks.
    expect(screen.queryByText('Higher.')).toBeNull();
    expect(screen.queryByText('Braced or cabled.')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Need a nudge?' }));
    expect(screen.getByText('Higher.')).toBeTruthy();
    expect(screen.queryByText('Braced or cabled.')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Need a nudge?' }));
    expect(screen.getByText('Braced or cabled.')).toBeTruthy();
    // The last level is out: no more button, just the end note.
    expect(screen.queryByRole('button', { name: 'Need a nudge?' })).toBeNull();
    expect(screen.getByText('That is every hint.')).toBeTruthy();
  });

  it('shows no hint control when the riddle has none', async () => {
    render(
      <RiddleDetailScreen
        snapshot={snapshot()}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Need a nudge?' })).toBeNull();
  });

  it('starts a different riddle with its hints hidden again', async () => {
    // Routing reuses the screen instance for the next riddle, so a
    // revealed count carried over would open the new ladder for free.
    const twoRiddles = {
      riddles: [
        { id: 'riddle-1', state: 'unsolved', text: 'First', hints: ['One.', 'Two.'] },
        { id: 'riddle-2', state: 'unsolved', text: 'Second', hints: ['A.', 'B.'] },
      ],
      submissions: [],
      me: { restriction: { level: 0 } },
    };
    const { rerender } = render(
      <RiddleDetailScreen
        snapshot={twoRiddles}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Need a nudge?' }));
    expect(screen.getByText('One.')).toBeTruthy();

    rerender(
      <RiddleDetailScreen
        snapshot={twoRiddles}
        copy={copy}
        riddleId="riddle-2"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    expect(screen.queryByText('A.')).toBeNull();
    expect(screen.queryByText('B.')).toBeNull();
    expect(screen.getByRole('button', { name: 'Need a nudge?' })).toBeTruthy();
  });

  it('does not offer submission when the player is submission-banned', async () => {    render(
      <RiddleDetailScreen
        snapshot={snapshot({ restrictionLevel: 3 })}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    expect(screen.getByText('Submissions paused')).toBeTruthy();
    await waitFor(() => expect(mocks.api.drawer).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Submit evidence' })).toBeNull();
  });

  it('acknowledges the strike notice and refreshes the snapshot', async () => {
    render(<StrikeNoticeScreen />);

    const acknowledge = screen.getByRole('button', { name: 'I understand' });
    fireEvent.click(acknowledge);

    await waitFor(() => {
      expect(mocks.api.noticeAck).toHaveBeenCalledTimes(1);
      expect(mocks.refresh).toHaveBeenCalledTimes(1);
    });
  });

  it('offers a retry from the connection-error screen', () => {
    const onRetry = vi.fn();
    render(
      <ConnectionErrorScreen
        message="Could not reach the server. Check your connection."
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText('Connection Failed')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('leaves the invite when the player stays on their team', async () => {
    window.history.replaceState(null, '', '/t/invite-token');
    mocks.api.inviteInfo.mockResolvedValue({
      team_name: 'GCPD',
      event_name: 'The Hunt',
    });
    mocks.api.redeemInvite.mockResolvedValue({ error: 'switch_needs_confirm' });

    render(<TeamJoinScreen token="invite-token" copy={copy} />);

    const codename = await screen.findByLabelText('Codename');
    fireEvent.input(codename, { target: { value: 'Robin' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the Team' }));

    const stay = await screen.findByRole('button', { name: 'Stay' });
    fireEvent.click(stay);

    await waitFor(() => expect(window.location.pathname).toBe('/'));
    expect(mocks.refresh).toHaveBeenCalled();
  });

  it('re-enables the warning controls when the refresh fails', async () => {
    window.history.replaceState(null, '', '/t/invite-token');
    mocks.api.inviteInfo.mockResolvedValue({
      team_name: 'GCPD',
      event_name: 'The Hunt',
    });
    mocks.api.redeemInvite.mockResolvedValue({ error: 'switch_needs_confirm' });
    mocks.refresh.mockRejectedValueOnce(new Error('offline'));

    render(<TeamJoinScreen token="invite-token" copy={copy} />);

    const codename = await screen.findByLabelText('Codename');
    fireEvent.input(codename, { target: { value: 'Robin' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the Team' }));

    const stay = await screen.findByRole('button', { name: 'Stay' });
    fireEvent.click(stay);

    await waitFor(() => expect(stay.disabled).toBe(false));
    expect(window.location.pathname).toBe('/');
  });

  it('switches team only after the warning is confirmed', async () => {
    window.history.replaceState(null, '', '/t/invite-token');
    mocks.api.inviteInfo.mockResolvedValue({
      team_name: 'GCPD',
      event_name: 'The Hunt',
    });
    mocks.api.redeemInvite
      .mockResolvedValueOnce({ error: 'switch_needs_confirm' })
      .mockResolvedValueOnce({ ok: true });

    render(<TeamJoinScreen token="invite-token" copy={copy} />);

    const codename = await screen.findByLabelText('Codename');
    fireEvent.input(codename, { target: { value: 'Robin' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the Team' }));

    const switchTeam = await screen.findByRole('button', { name: 'Switch team' });
    fireEvent.click(switchTeam);

    await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
    expect(mocks.api.redeemInvite).toHaveBeenLastCalledWith(
      'invite-token',
      'Robin',
      '',
      true,
    );
    expect(window.location.pathname).toBe('/');
  });
});

describe('keyboard and screen-reader access', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.api.drawer.mockResolvedValue([]);
    mocks.refresh.mockResolvedValue(undefined);
  });

  it('exposes each riddle tile as a button that opens the riddle', () => {
    const onOpenRiddle = vi.fn();
    render(
      <RiddleListScreen snapshot={snapshot()} copy={copy} onOpenRiddle={onOpenRiddle} />,
    );

    const tile = screen.getByRole('button', { name: 'Open riddle: Find the signal' });
    fireEvent.click(tile);
    expect(onOpenRiddle).toHaveBeenCalledWith('riddle-1');
  });

  it('names a solved riddle tile by its state', () => {
    render(
      <RiddleListScreen
        snapshot={snapshot({ riddleState: 'verified' })}
        copy={copy}
        onOpenRiddle={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Riddle solved: Find the signal' })).toBeTruthy();
  });

  it("names the drawer's file input and thumbnails for assistive tech", async () => {
    mocks.api.drawer.mockResolvedValue([
      { id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' },
    ]);
    render(<DrawerScreen snapshot={snapshot()} copy={copy} />);

    expect(screen.getByLabelText('Add a photo')).toBeTruthy();
    const photo = await screen.findByRole('img', { name: 'Your evidence photo' });
    expect(photo.getAttribute('src')).toBe('/api/evidence/ev-1/photo');
  });

  it('marks the selected evidence and enables submission', async () => {
    mocks.api.drawer.mockResolvedValue([
      { id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' },
      { id: 'ev-2', photo_url: '/api/evidence/ev-2/photo' },
    ]);
    render(
      <RiddleDetailScreen
        snapshot={snapshot()}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    const first = await screen.findByRole('button', { name: 'Evidence photo 1' });
    const second = screen.getByRole('button', { name: 'Evidence photo 2' });
    expect(first.getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(second);
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByRole('button', { name: 'Submit evidence' }).disabled).toBe(false);
  });

  it('opened from a riddle, the drawer tags the upload and hands back the photo (ADR 0036)', async () => {
    mocks.api.upload = vi.fn().mockResolvedValue({ id: 'ev-new' });
    const onUploadedFor = vi.fn();
    const onReturn = vi.fn();
    render(
      <DrawerScreen
        snapshot={snapshot()}
        copy={copy}
        returnTo="riddle-1"
        onReturn={onReturn}
        onUploadedFor={onUploadedFor}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Back to riddle 1' }));
    expect(onReturn).toHaveBeenCalledTimes(1);

    const file = new File(['x'], 'shot.jpg', { type: 'image/jpeg' });
    fireEvent.change(screen.getByLabelText('Add a photo'), { target: { files: [file] } });
    await waitFor(() => expect(onUploadedFor).toHaveBeenCalledWith('ev-new'));
    expect(mocks.api.upload).toHaveBeenCalledWith(file, 'riddle-1');
    delete mocks.api.upload;
  });

  it('does not tag or return to a riddle removed while the drawer was open', async () => {
    mocks.api.upload = vi.fn().mockResolvedValue({ id: 'ev-new' });
    const onUploadedFor = vi.fn();
    render(
      <DrawerScreen
        snapshot={snapshot()}
        copy={copy}
        returnTo="riddle-gone"
        onReturn={vi.fn()}
        onUploadedFor={onUploadedFor}
      />,
    );

    expect(screen.queryByRole('button', { name: /Back to riddle/ })).toBeNull();
    const file = new File(['x'], 'shot.jpg', { type: 'image/jpeg' });
    fireEvent.change(screen.getByLabelText('Add a photo'), { target: { files: [file] } });
    await waitFor(() => expect(mocks.api.upload).toHaveBeenCalledWith(file, undefined));
    await waitFor(() => expect(mocks.api.drawer).toHaveBeenCalledTimes(2));
    expect(onUploadedFor).not.toHaveBeenCalled();
    delete mocks.api.upload;
  });

  it('offers a new photo on a riddle whose drawer is not empty, and seeds a returned selection', async () => {
    mocks.api.drawer.mockResolvedValue([
      { id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' },
      { id: 'ev-2', photo_url: '/api/evidence/ev-2/photo' },
    ]);
    const onOpenDrawer = vi.fn();
    render(
      <RiddleDetailScreen
        snapshot={snapshot()}
        copy={copy}
        riddleId="riddle-1"
        initialSelected="ev-2"
        onBack={vi.fn()}
        onOpenDrawer={onOpenDrawer}
      />,
    );

    const second = await screen.findByRole('button', { name: 'Evidence photo 2' });
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Submit evidence' }).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Take a new photo' }));
    expect(onOpenDrawer).toHaveBeenCalledTimes(1);
  });

  it('greys out photos already pending or solved on another riddle (ADR 0035)', async () => {
    mocks.api.drawer.mockResolvedValue([
      { id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' },
      { id: 'ev-2', photo_url: '/api/evidence/ev-2/photo' },
      { id: 'ev-3', photo_url: '/api/evidence/ev-3/photo' },
    ]);
    const snap = snapshot();
    snap.riddles.push(
      { id: 'riddle-2', state: 'pending', text: 'Second', hints: [] },
      { id: 'riddle-3', state: 'verified', text: 'Third', hints: [] },
    );
    snap.submissions = [
      { id: 's3', riddle_id: 'riddle-2', evidence_item_id: 'ev-1', status: 'pending' },
      { id: 's2', riddle_id: 'riddle-3', evidence_item_id: 'ev-2', status: 'verified' },
      // A rejected submission frees its photo.
      { id: 's1', riddle_id: 'riddle-2', evidence_item_id: 'ev-3', status: 'not_found' },
    ];
    render(
      <RiddleDetailScreen
        snapshot={snap}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    const pending = await screen.findByRole('button', { name: 'Evidence photo 1, Scanning riddle 2' });
    const solved = screen.getByRole('button', { name: 'Evidence photo 2, Solved riddle 3' });
    const free = screen.getByRole('button', { name: 'Evidence photo 3' });
    expect(pending.disabled).toBe(true);
    expect(pending.classList.contains('pending')).toBe(true);
    expect(solved.disabled).toBe(true);
    expect(free.disabled).toBe(false);

    fireEvent.click(free);
    expect(free.getAttribute('aria-pressed')).toBe('true');
  });

  it('explains a photo a teammate took in the meantime', async () => {
    mocks.api.drawer.mockResolvedValue([{ id: 'ev-1', photo_url: '/api/evidence/ev-1/photo' }]);
    mocks.api.submit = vi.fn().mockResolvedValue({
      error: 'evidence_in_use', message: 'In use', riddle_id: 'riddle-1', status: 'pending',
    });
    render(
      <RiddleDetailScreen
        snapshot={snapshot()}
        copy={copy}
        riddleId="riddle-1"
        onBack={vi.fn()}
        onOpenDrawer={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Evidence photo 1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Submit evidence' }));
    expect(await screen.findByText('Already on riddle 1')).toBeTruthy();
    expect(mocks.refresh).toHaveBeenCalled();
    delete mocks.api.submit;
  });

  it('exposes the strike notice as a labelled alert dialog that holds focus', () => {
    render(<StrikeNoticeScreen />);

    const dialog = screen.getByRole('alertdialog', { name: 'A submission was removed' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');

    const acknowledge = screen.getByRole('button', { name: 'I understand' });
    expect(document.activeElement).toBe(acknowledge);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(acknowledge);
  });

  it('keeps the acknowledge button focusable while the ack is pending', async () => {
    let resolveAck;
    mocks.api.noticeAck.mockReturnValue(new Promise((resolve) => { resolveAck = resolve; }));
    render(<StrikeNoticeScreen />);

    const acknowledge = screen.getByRole('button', { name: 'I understand' });
    fireEvent.click(acknowledge);
    await waitFor(() => expect(mocks.api.noticeAck).toHaveBeenCalledTimes(1));

    expect(acknowledge.getAttribute('aria-disabled')).toBe('true');
    expect(acknowledge.disabled).toBe(false);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(acknowledge);

    resolveAck({ ok: true });
    await waitFor(() => expect(acknowledge.getAttribute('aria-disabled')).toBe('false'));
  });

  it('restores focus when the strike notice clears', () => {
    const outside = document.createElement('button');
    document.body.appendChild(outside);
    outside.focus();

    const { unmount } = render(<StrikeNoticeScreen />);
    expect(document.activeElement).not.toBe(outside);

    unmount();
    expect(document.activeElement).toBe(outside);
    outside.remove();
  });
});
