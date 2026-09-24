// Whether, and how, to suggest installing the app (TKT-01M390Y0VQ).
//
// Installing matters most on an iPhone, where the installed app gets a
// full screen and a home-screen icon but keeps its own storage apart from
// Safari's (design.md): a player who joins in Safari and installs
// afterwards opens the app to a blank join screen. So the suggestion comes
// on the join screen, before joining, and names the join code they will
// need in the app.
//
// iOS never offers an install prompt, so there it is instructions only.
// Chrome on Android fires `beforeinstallprompt`, which we hold on to so
// the hint can offer a real Install button; the installed app there
// shares the browser's storage, so no warning is needed.

const DISMISSED = 'arkham.installHint.dismissed';

let deferredPrompt = null;
const listeners = new Set();

// Chrome fires beforeinstallprompt once, often before the join screen
// mounts, so the listener is registered when this module loads.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    listeners.forEach((fn) => fn());
  });
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    listeners.forEach((fn) => fn());
  });
}

export function onInstallAvailabilityChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// 'installed' | 'ios' | 'prompt' | null (nothing to suggest).
export function installMode(win = window) {
  const nav = win.navigator;
  const standalone =
    nav.standalone === true || win.matchMedia?.('(display-mode: standalone)').matches;
  if (standalone) return 'installed';
  // iPadOS reports itself as a Mac; a Mac with touch points is an iPad.
  const ios =
    /iPhone|iPad|iPod/.test(nav.userAgent) ||
    (nav.platform === 'MacIntel' && nav.maxTouchPoints > 1);
  if (ios) return 'ios';
  if (deferredPrompt) return 'prompt';
  return null;
}

export async function promptInstall() {
  const prompt = deferredPrompt;
  if (!prompt) return false;
  deferredPrompt = null;
  await prompt.prompt();
  const choice = await prompt.userChoice;
  listeners.forEach((fn) => fn());
  return choice?.outcome === 'accepted';
}

export function hintDismissed() {
  try {
    return window.localStorage.getItem(DISMISSED) === '1';
  } catch {
    return false; // Private mode can refuse storage; show the hint.
  }
}

export function dismissHint() {
  try {
    window.localStorage.setItem(DISMISSED, '1');
  } catch {
    // Private mode: the hint comes back next visit, which is harmless.
  }
}
