// Resize-text check (WCAG 1.4.4) against the built app.
//
// Browser text zoom doubles every rem in the theme. Content must reflow
// without a horizontal scrollbar and the controls must stay operable, so
// this drives the board and the detail screen at 200% and measures.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

let codes;
let admin;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);

  const eventResponse = await admin.post('/api/admin/events', {
    data: { name: 'Resize Text Hunt', leaderboard_visibility: 'live' },
  });
  expect(eventResponse.status()).toBe(201);
  const event = await eventResponse.json();

  const riddleResponse = await admin.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the thing', sort_order: 1 },
  });
  expect(riddleResponse.status()).toBe(201);

  const openResponse = await admin.post(`/api/admin/events/${event.id}/open`);
  expect(openResponse.ok()).toBeTruthy();
  codes = { join: event.join_code };
});

test.afterAll(async () => {
  await admin?.dispose();
});

async function horizontalOverflow(page) {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test('the board and detail stay usable at 200% text zoom', async ({ page }) => {
  await page.goto(`/j/${codes.join}`);
  await page.getByLabel('Codename').fill('Robin');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();

  // Doubling the root font-size doubles every rem in the theme, the
  // browser's own text-zoom behaviour for a rem-based scale.
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%';
  });

  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);

  const tile = page.getByRole('button', { name: 'Open riddle: Find the thing' });
  await expect(tile).toBeVisible();
  await tile.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Find the thing' })).toBeVisible();

  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
});
