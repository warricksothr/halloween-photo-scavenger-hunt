import { describe, expect, it } from 'vitest';

import { loadTheme } from './theme';

describe('theme loader', () => {
  it('falls back to the Arkham pack when an event names a missing theme', async () => {
    await expect(loadTheme('missing-theme')).resolves.toMatchObject({ name: 'arkham' });
  });
});
