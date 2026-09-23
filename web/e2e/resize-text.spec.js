// Resize-text check (WCAG 1.4.4) against the built app.
//
// Browser text zoom doubles every rem in the theme. Content must reflow
// without a horizontal scrollbar and the controls must stay operable, so
// this drives the board and the detail screen at 200% and measures.
import { expect, test } from '@playwright/test';

const ADMIN_USERNAME = 'browser-test-admin';
const ADMIN_PASSWORD = 'browser-test-only';
const BASE_URL = 'http://127.0.0.1:4173';

let codes;
let adminApi;
let csrf;

test.beforeAll(async ({ playwright }) => {
  adminApi = await playwright.request.newContext({ baseURL: BASE_URL });

  // The API requires a signed CSRF token on every mutation: a safe GET
  // plants the cookie, then the value rides the X-CSRF-Token header.
  await adminApi.get('/api/health');
  const { cookies } = await adminApi.storageState();
  csrf = cookies.find((cookie) => cookie.name === 'arkham_csrf')?.value;
  const headers = { 'X-CSRF-Token': csrf };

  const login = await adminApi.post('/api/admin/login', {
    headers,
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();

  const eventResponse = await adminApi.post('/api/admin/events', {
    headers,
    data: { name: 'Resize Text Hunt', leaderboard_visibility: 'live' },
  });
  expect(eventResponse.status()).toBe(201);
  const event = await eventResponse.json();

  const riddleResponse = await adminApi.post(`/api/admin/events/${event.id}/riddles`, {
    headers,
    data: { text: 'Find the thing', sort_order: 1 },
  });
  expect(riddleResponse.status()).toBe(201);

  const openResponse = await adminApi.post(`/api/admin/events/${event.id}/open`, { headers });
  expect(openResponse.ok()).toBeTruthy();
  codes = { join: event.join_code };
});

test.afterAll(async () => {
  await adminApi?.dispose();
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
