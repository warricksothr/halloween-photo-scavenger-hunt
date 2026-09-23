import { describe, expect, it } from 'vitest';

import { defaultCopy, loadTheme } from './theme';

describe('theme loader', () => {
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
});
