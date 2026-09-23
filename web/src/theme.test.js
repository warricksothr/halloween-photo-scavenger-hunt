import { afterEach, describe, expect, it } from 'vitest';

import { defaultCopy, loadTheme, themeStylesheets } from './theme';

describe('theme loader', () => {
  afterEach(() => {
    document.head.querySelectorAll('style[data-theme]').forEach((node) => node.remove());
  });

  it('falls back to the Arkham pack when an event names a missing theme', async () => {
    await expect(loadTheme('missing-theme')).resolves.toMatchObject({ name: 'arkham' });
  });

  it('exposes the default pack copy for pre-event surfaces', () => {
    expect(defaultCopy().name).toBe('arkham');
    expect(defaultCopy().screens.boot.loading).toBeTruthy();
  });

  it('removes the previous pack stylesheet when the theme is switched', async () => {
    await loadTheme('arkham');
    const first = document.head.querySelector('style[data-theme="arkham"]');
    expect(first).toBeTruthy();

    await loadTheme('missing-theme');

    const second = document.head.querySelector('style[data-theme="arkham"]');
    expect(second).toBeTruthy();
    expect(second).not.toBe(first);
    expect(first.isConnected).toBe(false);
    expect(document.head.querySelectorAll('style[data-theme]')).toHaveLength(1);
  });

  it('keeps the latest pack when overlapping loads resolve out of order', async () => {
    const key = './themes/arkham/theme.css';
    const original = themeStylesheets[key];
    const resolvers = [];
    themeStylesheets[key] = () => new Promise((resolve) => resolvers.push(resolve));

    try {
      const first = loadTheme('arkham');
      const second = loadTheme('missing-theme');

      // The second request finishes first; the first resolves later and must
      // not overwrite it.
      resolvers[1]('/* second */');
      await second;
      resolvers[0]('/* first */');
      await first;

      const nodes = document.head.querySelectorAll('style[data-theme]');
      expect(nodes).toHaveLength(1);
      expect(nodes[0].textContent).toBe('/* second */');
    } finally {
      themeStylesheets[key] = original;
    }
  });

  it('resolves a superseded load only after the winning pack lands', async () => {
    const key = './themes/arkham/theme.css';
    const original = themeStylesheets[key];
    const resolvers = [];
    themeStylesheets[key] = () => new Promise((resolve) => resolvers.push(resolve));

    try {
      const first = loadTheme('arkham');
      const second = loadTheme('missing-theme');

      let firstSettled = false;
      first.then(() => {
        firstSettled = true;
      });

      // The older request resolves while the newer one is still in flight;
      // it must wait for the winner instead of resolving with its own copy.
      resolvers[0]('/* first */');
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(firstSettled).toBe(false);

      resolvers[1]('/* second */');
      await Promise.all([first, second]);
      expect(firstSettled).toBe(true);
      expect(document.head.querySelectorAll('style[data-theme]')).toHaveLength(1);
    } finally {
      themeStylesheets[key] = original;
    }
  });
});
