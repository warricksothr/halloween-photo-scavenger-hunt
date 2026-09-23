import { expect, test } from '@playwright/test';

const ADMIN_USERNAME = 'browser-test-admin';
const ADMIN_PASSWORD = 'browser-test-only';
const BASE_URL = 'http://127.0.0.1:4173';
const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

let codes;
let adminApi;

test.beforeAll(async ({ playwright }) => {
  adminApi = await playwright.request.newContext({ baseURL: BASE_URL });

  const login = await adminApi.post('/api/admin/login', {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();

  const eventResponse = await adminApi.post('/api/admin/events', {
    data: { name: 'Browser Smoke Hunt', leaderboard_visibility: 'live' },
  });
  expect(eventResponse.status()).toBe(201);
  const event = await eventResponse.json();

  const riddleResponse = await adminApi.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the thing', sort_order: 1 },
  });
  expect(riddleResponse.status()).toBe(201);

  const openResponse = await adminApi.post(`/api/admin/events/${event.id}/open`);
  expect(openResponse.ok()).toBeTruthy();
  codes = { join: event.join_code, mod: event.mod_code };
});

test.afterAll(async () => {
  await adminApi?.dispose();
});

test('player and moderator complete the built game loop', async ({ browser }) => {
  const playerContext = await browser.newContext();
  const moderatorContext = await browser.newContext();
  const player = await playerContext.newPage();
  const moderator = await moderatorContext.newPage();

  try {
    await player.goto(`/j/${codes.join}`);
    await expect(
      player.getByRole('heading', { name: 'Gotham Needs You' }),
    ).toBeVisible();
    await player.getByLabel('Codename').fill('Batman');
    await player.getByLabel('Device label (optional)').fill("Batman's phone");
    await player.getByRole('button', { name: 'Join the Hunt' }).click();

    await expect(
      player.getByRole('heading', { name: 'Riddle Board' }),
    ).toBeVisible();
    await expect(player.getByText('Batman', { exact: true }).first()).toBeVisible();

    await player.getByRole('button', { name: 'Open riddle: Find the thing' }).click();
    await expect(
      player.getByRole('heading', { name: 'Find the thing' }),
    ).toBeVisible();
    await expect(
      player.getByRole('button', { name: /drawer is empty/ }),
    ).toBeVisible();
    await player.getByRole('button', { name: /drawer is empty/ }).click();

    await expect(
      player.getByRole('heading', { name: 'Evidence Drawer' }),
    ).toBeVisible();
    await player.getByLabel('Add a photo').setInputFiles({
      name: 'synthetic-evidence.png',
      mimeType: 'image/png',
      buffer: PHOTO,
    });
    await expect(
      player.getByRole('img', { name: 'Your evidence photo' }),
    ).toHaveCount(1);

    await player.getByRole('link', { name: 'Riddles' }).click();
    await player.getByRole('button', { name: 'Open riddle: Find the thing' }).click();
    await expect(
      player.getByRole('button', { name: 'Submit to the Batcomputer' }),
    ).toBeVisible();
    await player.getByRole('button', { name: /^Evidence photo/ }).first().click();
    await player.getByRole('button', { name: 'Submit to the Batcomputer' }).click();
    await expect(player.getByText('SCANNING…')).toBeVisible();

    await moderator.goto(`/m/${codes.mod}`);
    await expect(
      moderator.getByRole('heading', { name: 'Moderator Console' }),
    ).toBeVisible();
    await moderator.getByRole('button', { name: 'Open the console' }).click();
    await expect(
      moderator.getByRole('heading', { name: 'Analysis Queue' }),
    ).toBeVisible();
    await expect(moderator.getByText('1 pending')).toBeVisible();
    await moderator.getByText('#1 — Batman', { exact: true }).click();
    await expect(
      moderator.getByRole('button', { name: '✓ Riddle Solved' }),
    ).toBeVisible();
    await moderator.getByRole('button', { name: '✓ Riddle Solved' }).click();
    await expect(
      moderator.getByText('Queue is clear. Nothing awaiting review.'),
    ).toBeVisible();

    await expect(player.getByText('RIDDLE SOLVED.')).toBeVisible();
    await player.getByRole('button', { name: '← Back to the board' }).click();
    await expect(player.getByText('1/1', { exact: true })).toBeVisible();
    await player.getByRole('link', { name: 'Standings' }).click();
    await expect(
      player.getByRole('heading', { name: 'Standings' }),
    ).toBeVisible();
    const standingsRow = player.getByRole('listitem').first();
    await expect(standingsRow).toContainText('Batman');
    await expect(standingsRow).toContainText('1');
  } finally {
    await Promise.all([playerContext.close(), moderatorContext.close()]);
  }
});
