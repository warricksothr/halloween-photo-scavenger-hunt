import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

let codes;
let admin;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);

  const eventResponse = await admin.post('/api/admin/events', {
    data: { name: 'Browser Smoke Hunt', leaderboard_visibility: 'live' },
  });
  expect(eventResponse.status()).toBe(201);
  const event = await eventResponse.json();

  const riddleResponse = await admin.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the thing', sort_order: 1 },
  });
  expect(riddleResponse.status()).toBe(201);

  const openResponse = await admin.post(`/api/admin/events/${event.id}/open`);
  expect(openResponse.ok()).toBeTruthy();
  codes = { join: event.join_code, mod: event.mod_code };
});

test.afterAll(async () => {
  await admin?.dispose();
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
    // Saved, the photo goes straight back to the riddle that asked for it,
    // already selected (ADR 0036).
    await expect(
      player.getByRole('heading', { name: 'Find the thing' }),
    ).toBeVisible();
    await expect(
      player.getByRole('button', { name: /^Evidence photo 1/ }),
    ).toHaveAttribute('aria-pressed', 'true');
    await player.getByRole('button', { name: 'Submit to the Batcomputer' }).click();
    await expect(player.getByText('SCANNING…')).toBeVisible();

    // The mod link auto-attempts, finds no moderator session, and sends the
    // browser through the stub IdP; the callback returns here and the
    // console opens. Wait for the queue, not the sign-in screen.
    await moderator.goto(`/m/${codes.mod}`);
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

    // The Log view (ADR 0044) names the call just made, with its photo.
    await moderator.getByRole('button', { name: 'Log', exact: true }).click();
    const log = moderator.getByRole('list', { name: 'Moderation log' });
    const verdictRow = log.getByRole('listitem').filter({ hasText: 'marked Batman' });
    await expect(verdictRow).toContainText("photo for Riddle #1 solved");
    await verdictRow.getByRole('button', { name: 'Photo' }).click();
    const lightbox = moderator.getByRole('dialog');
    await expect(lightbox).toBeVisible();
    await lightbox.getByRole('button', { name: 'Close' }).click();
    await expect(lightbox).toHaveCount(0);
    await moderator.getByRole('button', { name: 'Queue', exact: true }).click();

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
