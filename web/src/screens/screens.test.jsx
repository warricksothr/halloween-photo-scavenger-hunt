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
    detail: {
      alreadyScanning: 'Already scanning.',
      back: 'Back',
      emptyDrawer: 'Drawer empty',
      evidenceOption: (position) => `Evidence photo ${position}`,
      loading: 'Loading drawer',
      pickEvidence: 'Submit evidence',
      submit: 'Submit evidence',
      submitting: 'Submitting',
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

function snapshot({ riddleState = 'unsolved', restrictionLevel = 0 } = {}) {
  return {
    riddles: [{ id: 'riddle-1', state: riddleState, text: 'Find the signal' }],
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

  it('does not offer submission when the player is submission-banned', async () => {
    render(
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

  it('exposes the strike notice as a labelled alert dialog that holds focus', () => {
    render(<StrikeNoticeScreen />);

    const dialog = screen.getByRole('alertdialog', { name: 'A submission was removed' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');

    const acknowledge = screen.getByRole('button', { name: 'I understand' });
    expect(document.activeElement).toBe(acknowledge);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(acknowledge);
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
