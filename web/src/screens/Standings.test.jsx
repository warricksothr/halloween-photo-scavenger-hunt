import { fireEvent, render, screen } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: { recap: vi.fn() },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { StandingsScreen } from './Standings';

const copy = {
  recap: {},
  screens: {
    standings: {
      headline: 'Standings',
      sealed: 'Sealed',
      empty: 'EMPTY_BOARD',
      loading: 'LOADING_REPORT',
      error: 'FALLBACK_ERROR',
      retry: 'Retry',
      noWinner: 'No winner',
      caseClosed: 'Case Closed',
      caseClosedSubtext: () => 'closed',
      recapHeadline: 'Recap',
      you: '(you)',
    },
  },
};

function closed() {
  return { event: { status: 'closed' } };
}

describe('closed standings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows an error with a working retry instead of loading forever', async () => {
    mocks.api.recap
      .mockResolvedValueOnce({ error: 'network_error', message: 'OFFLINE' })
      .mockResolvedValueOnce({ standings: [], total_riddles: 3, timeline: [] });

    render(<StandingsScreen snapshot={closed()} copy={copy} />);

    expect(await screen.findByText('OFFLINE')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Case Closed')).toBeTruthy();
    expect(mocks.api.recap).toHaveBeenCalledTimes(2);
  });

  it('falls back to the pack error line when the failure carries no message', async () => {
    mocks.api.recap.mockResolvedValue({ error: 'request_failed' });

    render(<StandingsScreen snapshot={closed()} copy={copy} />);

    expect(await screen.findByText('FALLBACK_ERROR')).toBeTruthy();
  });

  it('shows the error state when the recap request rejects', async () => {
    mocks.api.recap.mockRejectedValue(new Error('transport down'));

    render(<StandingsScreen snapshot={closed()} copy={copy} />);

    expect(await screen.findByText('FALLBACK_ERROR')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('renders the empty state when no team is on the final board', async () => {
    mocks.api.recap.mockResolvedValue({ standings: [], total_riddles: 3, timeline: [] });

    render(<StandingsScreen snapshot={closed()} copy={copy} />);

    expect(await screen.findByText('EMPTY_BOARD')).toBeTruthy();
  });

  it('tells a reopened round in the timeline (ADR 0042)', async () => {
    mocks.api.recap.mockResolvedValue({
      standings: [],
      total_riddles: 1,
      timeline: [
        { kind: 'closed', at: 100, expired_pending: 0 },
        { kind: 'reopened', at: 200 },
        { kind: 'closed', at: 300, expired_pending: 0 },
      ],
    });
    const withRecap = {
      ...copy,
      recap: { closed: () => 'CLOSED_LINE', reopened: () => 'REOPENED_LINE' },
    };

    render(<StandingsScreen snapshot={closed()} copy={withRecap} />);

    expect(await screen.findByText('REOPENED_LINE')).toBeTruthy();
    expect(screen.getAllByText('CLOSED_LINE')).toHaveLength(2);
  });
});

describe('live standings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exposes the board as a list of rows', () => {
    const snapshot = {
      event: { status: 'open' },
      leaderboard: [
        { team_id: 't1', team: 'Batman', rank: 1, score: 2, you: true },
        { team_id: 't2', team: 'Robin', rank: 2, score: 1, you: false },
      ],
    };

    render(<StandingsScreen snapshot={snapshot} copy={copy} />);

    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('Batman');
  });
});
