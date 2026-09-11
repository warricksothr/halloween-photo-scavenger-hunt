import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    drawer: vi.fn(),
    noticeAck: vi.fn(),
  },
  refresh: vi.fn(),
}));

vi.mock('../api', () => ({ api: mocks.api }));
vi.mock('../store', () => ({ refresh: mocks.refresh }));

import { RiddleDetailScreen } from './RiddleDetail';
import { StrikeNoticeScreen } from './StrikeNotice';

const copy = {
  verdicts: {
    pending: { headline: 'SCANNING', subtext: 'Checking the evidence.' },
  },
  screens: {
    detail: {
      alreadyScanning: 'Already scanning.',
      back: 'Back',
      emptyDrawer: 'Drawer empty',
      loading: 'Loading drawer',
      pickEvidence: 'Submit evidence',
      submit: 'Submit evidence',
      submitting: 'Submitting',
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
});
