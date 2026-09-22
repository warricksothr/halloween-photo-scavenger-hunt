import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

// The shell policy's job is to make a redeploy reach a phone that is
// already running the old build. So this rewrites the built index.html
// on disk (a stand-in for a deploy) and proves the service worker serves
// it on the next navigation instead of the cached shell.
const INDEX = fileURLToPath(new URL('../dist/index.html', import.meta.url));
const MARKER = '<div id="deploy-marker">new build</div>';

test('a redeploy reaches a phone that already has the old shell', async ({ page }) => {
  const original = readFileSync(INDEX, 'utf8');

  await page.goto('/');
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);

  try {
    writeFileSync(INDEX, original.replace('</body>', `${MARKER}</body>`));

    await page.reload();
    await expect(page.locator('#deploy-marker')).toBeVisible();
  } finally {
    writeFileSync(INDEX, original);
  }
});
