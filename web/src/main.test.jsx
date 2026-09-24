import { screen, waitFor } from '@testing-library/preact';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  initErrorReporting: vi.fn(() => Promise.resolve(true)),
  getState: vi.fn(() => ({ phase: 'booting' })),
  refresh: vi.fn(),
  retry: vi.fn(),
  subscribe: vi.fn(() => () => {}),
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
  refresh: mocks.refresh,
  retry: mocks.retry,
  subscribe: mocks.subscribe,
}));

// The admin route reaches AdminScreen through AdminBoot; every other screen
// is imported by main.jsx, so each is stubbed to keep the module graph light.
vi.mock('./components/Header', () => ({ Header: () => null }));
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

  it('renders the boot line from the default theme pack', async () => {
    mocks.getState.mockReturnValue({ phase: 'booting' });

    await import('./main.jsx');

    await waitFor(() => expect(screen.getByText('BOOT_SENTINEL')).toBeTruthy());
  });
});
