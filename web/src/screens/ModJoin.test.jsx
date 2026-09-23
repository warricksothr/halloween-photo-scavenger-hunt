// The mod link's landing surface (S9CW): the three jobs — start OIDC,
// explain a refused sign-in, or open the console — each get a test.
import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modJoin: vi.fn(),
  oidcLoginUrl: vi.fn((next) => `OIDC:${next}`),
  navigate: vi.fn(),
}));

vi.mock('../api', () => ({ oidcLoginUrl: mocks.oidcLoginUrl }));
vi.mock('../store', () => ({ modJoin: mocks.modJoin }));

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

  it('tells the host they are on the wrong surface, with a way back', async () => {
    visit('/m/MODCODE1?sso=not_moderator');

    render(<ModJoinScreen navigate={mocks.navigate} />);

    expect(await screen.findByText(/signed in as the host/)).toBeTruthy();
    const hostLink = screen.getByText('Go to the host console');
    expect(hostLink.getAttribute('href')).toBe('/admin');
    expect(mocks.modJoin).not.toHaveBeenCalled();
  });

  it('opens the console from a typed code at /mod, via SSO when needed', async () => {
    visit('/mod');
    mocks.modJoin.mockResolvedValue({ unauthenticated: true });

    render(<ModJoinScreen navigate={mocks.navigate} />);

    const input = screen.getByLabelText('Moderator code');
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
