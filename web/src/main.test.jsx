import { fireEvent, screen, waitFor } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  initErrorReporting: vi.fn(() => Promise.resolve(true)),
  getState: vi.fn(() => ({ phase: 'booting' })),
  leaveModerator: vi.fn(),
  refresh: vi.fn(),
  retry: vi.fn(),
  subscribe: vi.fn(() => () => {}),
  switchGame: vi.fn(),
  defaultCopy: vi.fn(() => ({ screens: { boot: { loading: 'BOOT_SENTINEL' } } })),
}));

vi.mock('./errors', () => ({ initErrorReporting: mocks.initErrorReporting }));
vi.mock('./theme', () => ({
  DEFAULT_THEME: 'arkham',
  defaultCopy: mocks.defaultCopy,
  loadTheme: vi.fn(),
}));
vi.mock('./store', () => ({
  getState: mocks.getState,
  leaveModerator: mocks.leaveModerator,
  refresh: mocks.refresh,
  retry: mocks.retry,
  subscribe: mocks.subscribe,
  switchGame: mocks.switchGame,
}));

// The admin route reaches AdminScreen through AdminBoot; every other screen
// is imported by main.jsx, so each is stubbed to keep the module graph light.
// The header stub keeps its action so the console's Leave button can be clicked.
vi.mock('./components/Header', () => ({ Header: ({ action }) => <div>{action}</div> }));
vi.mock('./screens/Admin', () => ({ AdminScreen: () => null }));
vi.mock('./screens/ConnectionError', () => ({ ConnectionErrorScreen: () => null }));
vi.mock('./screens/Join', () => ({ JoinScreen: () => <div data-testid="join" /> }));
vi.mock('./screens/ModJoin', () => ({
  ModJoinScreen: () => <div data-testid="mod-join" />,
}));
vi.mock('./screens/TeamJoin', () => ({ TeamJoinScreen: () => null }));
vi.mock('./screens/ModConsole', () => ({ ModConsoleScreen: () => null }));
vi.mock('./screens/Lobby', () => ({ LobbyScreen: () => null }));
vi.mock('./screens/RiddleList', () => ({ RiddleListScreen: () => null }));
vi.mock('./screens/RiddleDetail', () => ({ RiddleDetailScreen: () => null }));
vi.mock('./screens/Drawer', () => ({ DrawerScreen: () => null }));
vi.mock('./screens/Standings', () => ({ StandingsScreen: () => null }));
vi.mock('./screens/Team', () => ({ TeamScreen: () => null }));
vi.mock('./screens/StrikeNotice', () => ({ StrikeNoticeScreen: () => null }));

describe('app entry', () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.initErrorReporting.mockClear();
    mocks.getState.mockReturnValue({ phase: 'booting' });
    document.body.innerHTML = '<div id="app"></div>';
  });

  afterEach(() => {
    window.history.replaceState({}, '', '/');
  });

  it('boots the reporter on the admin route, which has no player store', async () => {
    window.history.replaceState({}, '', '/admin');

    await import('./main.jsx');

    await waitFor(() => expect(mocks.initErrorReporting).toHaveBeenCalledTimes(1));
    // The admin console is a separate document; it must not boot the store.
    expect(mocks.subscribe).not.toHaveBeenCalled();
    expect(mocks.refresh).not.toHaveBeenCalled();
  });

  it('routes the bare /mod path to the moderator join screen', async () => {
    window.history.replaceState({}, '', '/mod');
    mocks.getState.mockReturnValue({ phase: 'join' });

    await import('./main.jsx');

    await waitFor(() => expect(screen.getByTestId('mod-join')).toBeTruthy());
    expect(screen.queryByTestId('join')).toBeNull();
  });

  it('routes a mod link to the moderator join even over a ready player session', async () => {
    // TKT-01M394KVSC6GCC1EDW4NSXZRW3: the host who also plays opens the
    // mod link on the same phone; the link must join, not show the game.
    window.history.replaceState({}, '', '/m/MODCODE1');
    mocks.getState.mockReturnValue({
      phase: 'ready',
      role: 'player',
      snapshot: { event: { status: 'open', name: 'Party' }, me: { display_name: 'Robin' } },
      copy: {},
    });

    await import('./main.jsx');

    await waitFor(() => expect(screen.getByTestId('mod-join')).toBeTruthy());
  });

  it('offers a way out of the moderator console (ADR 0032)', async () => {
    window.history.replaceState({}, '', '/mod');
    mocks.getState.mockReturnValue({
      phase: 'ready',
      role: 'moderator',
      modEvent: { name: 'Party' },
      moderator: { id: 'mod-1', label: 'Drew' },
      copy: {},
    });

    await import('./main.jsx');

    fireEvent.click(await screen.findByRole('button', { name: 'Leave console' }));
    expect(mocks.leaveModerator).toHaveBeenCalledTimes(1);
  });

  it('offers Switch Case in the game and the lobby (ADR 0033)', async () => {
    for (const status of ['open', 'lobby']) {
      vi.resetModules();
      document.body.innerHTML = '<div id="app"></div>';
      mocks.switchGame.mockClear();
      mocks.getState.mockReturnValue({
        phase: 'ready',
        role: 'player',
        snapshot: {
          event: { status, name: 'Party' },
          me: { display_name: 'Robin', restriction: {} },
        },
        copy: { screens: { header: { switchGame: 'SWITCH_SENTINEL' } }, tabs: {} },
      });

      await import('./main.jsx');

      fireEvent.click(await screen.findByRole('button', { name: 'SWITCH_SENTINEL' }));
      expect(mocks.switchGame).toHaveBeenCalledTimes(1);
    }
  });

  it('pins the header and the tabs together at the top of the game (ADR 0034)', async () => {
    mocks.getState.mockReturnValue({
      phase: 'ready',
      role: 'player',
      snapshot: {
        event: { status: 'open', name: 'Party' },
        me: { display_name: 'Robin', restriction: {} },
      },
      copy: {
        screens: { header: { switchGame: 'SWITCH_SENTINEL' } },
        tabs: { riddles: 'Riddles', drawer: 'Drawer', team: 'Team', standings: 'Standings' },
      },
    });

    await import('./main.jsx');

    const switchCase = await screen.findByRole('button', { name: 'SWITCH_SENTINEL' });
    const bar = switchCase.closest('.top-bar');
    expect(bar).toBeTruthy();
    // The bar leads the frame, so the screen scrolls under it.
    expect(bar.parentElement.firstElementChild).toBe(bar);
    const tabs = [...bar.querySelectorAll('.tab-bar a')];
    expect(tabs.map((a) => a.textContent)).toEqual(['?Riddles', '▦Drawer', '⬡Team', '≡Standings']);
    expect(tabs[0].getAttribute('aria-current')).toBe('page');

    fireEvent.click(tabs[2]);
    await waitFor(() => expect(tabs[2].getAttribute('aria-current')).toBe('page'));
    expect(tabs[0].getAttribute('aria-current')).toBeNull();
  });

  it('renders the boot line from the default theme pack', async () => {
    mocks.getState.mockReturnValue({ phase: 'booting' });

    await import('./main.jsx');

    await waitFor(() => expect(screen.getByText('BOOT_SENTINEL')).toBeTruthy());
  });
});
