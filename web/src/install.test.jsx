import { fireEvent, render, screen } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { InstallHint } from './components/InstallHint';
import { installMode } from './install';

const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const ANDROID = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36';

function fakeWindow({ userAgent, standalone = false, displayStandalone = false, platform = '', maxTouchPoints = 0 }) {
  return {
    navigator: { userAgent, standalone, platform, maxTouchPoints },
    matchMedia: () => ({ matches: displayStandalone }),
  };
}

const copy = {
  screens: {
    join: {
      install: {
        headline: 'Install',
        iosSteps: 'Tap Share, then Add to Home Screen.',
        iosThen: (code) => (code ? `Join in the app with ${code}.` : 'Join in the app.'),
        promptBody: 'Add it to your home screen.',
        install: 'Install now',
        dismiss: 'Not now',
      },
    },
  },
};

function setUserAgent(value) {
  Object.defineProperty(window.navigator, 'userAgent', { value, configurable: true });
}

describe('install suggestion (TKT-01M390Y0VQ)', () => {
  beforeEach(() => {
    window.localStorage.clear();
    setUserAgent(ANDROID);
  });

  it('knows an iPhone, an iPad posing as a Mac, and an installed app', () => {
    expect(installMode(fakeWindow({ userAgent: IPHONE }))).toBe('ios');
    expect(installMode(fakeWindow({ userAgent: 'Macintosh', platform: 'MacIntel', maxTouchPoints: 5 }))).toBe('ios');
    expect(installMode(fakeWindow({ userAgent: IPHONE, standalone: true }))).toBe('installed');
    expect(installMode(fakeWindow({ userAgent: ANDROID, displayStandalone: true }))).toBe('installed');
    // A desktop or Android browser with no install prompt on offer.
    expect(installMode(fakeWindow({ userAgent: ANDROID }))).toBeNull();
  });

  it('on an iPhone, explains the steps and names the join code for the app', () => {
    setUserAgent(IPHONE);
    render(<InstallHint copy={copy} joinCode="ABCD2345" />);
    expect(screen.getByRole('heading', { name: 'Install' })).toBeTruthy();
    expect(screen.getByText('Join in the app with ABCD2345.')).toBeTruthy();
    // iOS has no prompt to trigger, so there is no Install button.
    expect(screen.queryByRole('button', { name: 'Install now' })).toBeNull();
  });

  it('stays dismissed once dismissed', () => {
    setUserAgent(IPHONE);
    const first = render(<InstallHint copy={copy} joinCode={null} />);
    fireEvent.click(screen.getByRole('button', { name: 'Not now' }));
    expect(screen.queryByRole('heading', { name: 'Install' })).toBeNull();
    first.unmount();
    render(<InstallHint copy={copy} joinCode={null} />);
    expect(screen.queryByRole('heading', { name: 'Install' })).toBeNull();
  });

  it('comes back on a page opened from a link with a code (ADR 0043)', () => {
    setUserAgent(IPHONE);
    const first = render(<InstallHint copy={copy} joinCode={null} />);
    fireEvent.click(screen.getByRole('button', { name: 'Not now' }));
    first.unmount();
    // A join or invite link: joining in Safari now would strand the
    // player outside the app, so the earlier "Not now" does not hold.
    const linked = render(<InstallHint copy={copy} joinCode="ABCD2345" fromLink />);
    expect(screen.getByText('Join in the app with ABCD2345.')).toBeTruthy();
    // "Not now" still hides it on this page.
    fireEvent.click(screen.getByRole('button', { name: 'Not now' }));
    expect(screen.queryByRole('heading', { name: 'Install' })).toBeNull();
    linked.unmount();
  });

  it("offers Chrome's install prompt when the browser makes one available", async () => {
    render(<InstallHint copy={copy} joinCode={null} />);
    expect(screen.queryByRole('heading', { name: 'Install' })).toBeNull();

    const prompt = vi.fn().mockResolvedValue(undefined);
    const event = new Event('beforeinstallprompt');
    Object.assign(event, { prompt, userChoice: Promise.resolve({ outcome: 'accepted' }) });
    window.dispatchEvent(event);

    const install = await screen.findByRole('button', { name: 'Install now' });
    fireEvent.click(install);
    await vi.waitFor(() => expect(prompt).toHaveBeenCalledTimes(1));
  });

  it('shows nothing in the installed app', () => {
    setUserAgent(IPHONE);
    Object.defineProperty(window.navigator, 'standalone', { value: true, configurable: true });
    render(<InstallHint copy={copy} joinCode={null} />);
    expect(screen.queryByRole('heading', { name: 'Install' })).toBeNull();
    delete window.navigator.standalone;
  });
});
