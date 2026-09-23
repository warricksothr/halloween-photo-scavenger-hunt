// Proves the player-facing screens read their strings from the active theme
// pack: each screen renders against a sentinel copy fixture, so a string
// baked into the component fails the assertion (TKT-01M33RFWWFJJJ7JP9JE7ZRE54K).
import { render, screen } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    inviteInfo: vi.fn(),
    recap: vi.fn(),
    team: vi.fn(),
  },
  join: vi.fn(),
  refresh: vi.fn(),
  copy: {
    verdicts: {},
    recap: {},
    tiles: {},
    screens: {
      boot: { loading: 'BOOT_SENTINEL' },
      join: {
        headline: 'JOIN_HEADLINE',
        subtext: 'JOIN_SUBTEXT',
        nameLabel: 'JOIN_NAME',
        deviceLabel: 'JOIN_DEVICE',
        codeLabel: 'JOIN_CODE_LABEL',
        codePlaceholder: 'JOIN_CODE_PH',
        devicePlaceholder: 'JOIN_DEVICE_PH',
        submit: 'JOIN_SUBMIT',
      },
      teamJoin: {
        headline: 'TEAMJOIN_HEADLINE',
        loading: 'TEAMJOIN_LOADING',
        unavailable: 'TEAMJOIN_UNAVAILABLE',
        expired: 'TEAMJOIN_EXPIRED',
        teamLine: () => 'TEAMJOIN_LINE',
        nameLabel: 'TEAMJOIN_NAME',
        join: 'TEAMJOIN_JOIN',
        switchHeadline: 'x',
        switchBody: 'x',
        stay: 'x',
        switchConfirm: 'x',
        full: 'x',
      },
      standings: {
        headline: 'STANDINGS_HEADLINE',
        sealed: 'x',
        empty: 'x',
        loading: 'STANDINGS_LOADING',
        noWinner: 'STANDINGS_NOWINNER',
        caseClosed: 'x',
        caseClosedSubtext: () => 'x',
        recapHeadline: 'x',
        you: 'x',
      },
      team: {
        headline: 'TEAM_HEADLINE',
        loading: 'TEAM_LOADING',
        lastSeen: (mins) => `TEAM_SEEN(${mins})`,
        namePlaceholder: 'x',
        operatives: 'x',
        editName: 'x',
        saveName: 'x',
        cancel: 'x',
        roster: 'x',
        you: 'x',
        recruit: 'x',
        createInvite: 'x',
        newCode: 'x',
        revoke: 'x',
        singleUse: 'x',
        expiresIn: 'x',
        teamFull: 'x',
        inviteNote: 'x',
      },
    },
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));
vi.mock('../store', () => ({ join: mocks.join, refresh: mocks.refresh }));
vi.mock('../theme', () => ({
  DEFAULT_THEME: 'arkham',
  loadTheme: vi.fn(async () => mocks.copy),
}));

import { JoinScreen } from './Join';
import { TeamJoinScreen } from './TeamJoin';
import { StandingsScreen } from './Standings';
import { TeamScreen } from './Team';

describe('game-facing copy comes from the theme pack', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    mocks.refresh.mockResolvedValue(undefined);
  });

  it('renders the join code labels and placeholders from copy', async () => {
    render(<JoinScreen />);

    expect(await screen.findByLabelText('JOIN_CODE_LABEL')).toBeTruthy();
    expect(screen.getByPlaceholderText('JOIN_CODE_PH')).toBeTruthy();
    expect(screen.getByPlaceholderText('JOIN_DEVICE_PH')).toBeTruthy();
  });

  it('renders the invite loading line from copy', async () => {
    mocks.api.inviteInfo.mockReturnValue(new Promise(() => {}));

    render(<TeamJoinScreen token="invite-token" />);

    expect(await screen.findByText('TEAMJOIN_LOADING')).toBeTruthy();
  });

  it('renders the invite-unavailable headline from copy', async () => {
    mocks.api.inviteInfo.mockResolvedValue({ error: 'bad_invite', message: 'nope' });

    render(<TeamJoinScreen token="invite-token" />);

    expect(await screen.findByText('TEAMJOIN_UNAVAILABLE')).toBeTruthy();
  });

  it('renders the closed-standings loading line from copy', () => {
    mocks.api.recap.mockReturnValue(new Promise(() => {}));

    render(
      <StandingsScreen snapshot={{ event: { status: 'closed' } }} copy={mocks.copy} />,
    );

    expect(screen.getByText('STANDINGS_LOADING')).toBeTruthy();
  });

  it('renders the no-winner fallback from copy', async () => {
    mocks.api.recap.mockResolvedValue({ standings: [], total_riddles: 3, timeline: [] });

    render(
      <StandingsScreen snapshot={{ event: { status: 'closed' } }} copy={mocks.copy} />,
    );

    expect(await screen.findByText('STANDINGS_NOWINNER')).toBeTruthy();
  });

  it('renders roster last-seen through the pack copy function', async () => {
    mocks.api.team.mockResolvedValue({
      team: { name: 'GCPD', size_limit: 4 },
      members: [{ id: 'm1', display_name: 'Robin', last_seen_at: null, you: true }],
      invites: [],
    });

    render(<TeamScreen snapshot={{ me: { display_name: 'Robin' } }} copy={mocks.copy} />);

    expect(await screen.findByText(/TEAM_SEEN\(null\)/)).toBeTruthy();
  });
});
