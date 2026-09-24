// The mod link's landing surface (S9CW): the three jobs — start OIDC,
// explain a refused sign-in, or open the console — each get a test.
import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modJoin: vi.fn(),
  oidcLoginUrl: vi.fn((next) => `OIDC:${next}`),
  navigate: vi.fn(),
  loadTheme: vi.fn(() => Promise.resolve({})),
}));

vi.mock('../api', () => ({ oidcLoginUrl: mocks.oidcLoginUrl }));
vi.mock('../store', () => ({ modJoin: mocks.modJoin }));
vi.mock('../theme', () => ({
  DEFAULT_THEME: 'arkham',
  loadTheme: mocks.loadTheme,
}));

import { ModJoinScreen } from './ModJoin';

function visit(path) {
  window.history.replaceState(null, '', path);
}

describe('moderator join', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.navigate.mockClear();
  });

  it('sends an unauthenticated link to SSO and comes back to the link', async () => {
    visit('/m/MODCODE1');
    mocks.modJoin.mockResolvedValue({ unauthenticated: true });

    render(<ModJoinScreen navigate={mocks.navigate} />);

    await waitFor(() =>
      expect(mocks.modJoin).toHaveBeenCalledWith('MODCODE1'),
    );
    expect(mocks.navigate).toHaveBeenCalledWith('OIDC:/m/MODCODE1');
  });

  it('explains a refused sign-in instead of retrying', async () => {
    visit('/m/MODCODE1?sso=not_authorized');

    render(<ModJoinScreen navigate={mocks.navigate} />);

    expect(await screen.findByText(/not a moderator of this event/)).toBeTruthy();
    expect(mocks.modJoin).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it('loads the default theme so the screen is styled before any session', async () => {
    visit('/mod');
    render(<ModJoinScreen navigate={mocks.navigate} />);
    expect(mocks.loadTheme).toHaveBeenCalledWith('arkham');
    expect(await screen.findByLabelText('Moderator code')).toBeTruthy();
  });

  it('treats an old host marker as no refusal and joins, since the host moderates', async () => {
    visit('/m/MODCODE1?sso=not_moderator');
    mocks.modJoin.mockResolvedValue({});
    render(<ModJoinScreen navigate={mocks.navigate} />);
    await waitFor(() => expect(mocks.modJoin).toHaveBeenCalledWith('MODCODE1'));
    expect(screen.queryByText(/signed in as the host/)).toBeNull();
  });

  it('upper-cases a code that arrives in the link', async () => {
    visit('/m/modcode1');
    mocks.modJoin.mockResolvedValue({ unauthenticated: true });
    render(<ModJoinScreen navigate={mocks.navigate} />);
    await waitFor(() => expect(mocks.modJoin).toHaveBeenCalledWith('MODCODE1'));
  });

  it('trims a typed code padded with spaces', async () => {
    visit('/mod');
    mocks.modJoin.mockResolvedValue({ unauthenticated: true });
    render(<ModJoinScreen navigate={mocks.navigate} />);
    fireEvent.input(await screen.findByLabelText('Moderator code'), {
      target: { value: '  code9 ' },
    });
    fireEvent.click(screen.getByText('Open the console'));
    await waitFor(() => expect(mocks.modJoin).toHaveBeenCalledWith('CODE9'));
  });

  it('opens the console from a typed code at /mod, via SSO when needed', async () => {
    visit('/mod');
    mocks.modJoin.mockResolvedValue({ unauthenticated: true });

    render(<ModJoinScreen navigate={mocks.navigate} />);

    const input = await screen.findByLabelText('Moderator code');
    fireEvent.input(input, { target: { value: 'code9' } });
    fireEvent.click(screen.getByText('Open the console'));

    await waitFor(() => expect(mocks.modJoin).toHaveBeenCalledWith('CODE9'));
    expect(mocks.navigate).toHaveBeenCalledWith('OIDC:/mod');
  });

  it('shows the server message when the code is wrong', async () => {
    visit('/m/BADCODE');
    mocks.modJoin.mockResolvedValue({
      error: 'bad_mod_code',
      message: 'That moderator link doesn\u2019t match any event.',
    });

    render(<ModJoinScreen navigate={mocks.navigate} />);

    expect(await screen.findByText(/doesn.t match any event/)).toBeTruthy();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });
});
