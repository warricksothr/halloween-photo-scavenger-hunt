// Back and the edge swipe move between the game's screens (ADR 0036,
// TKT-01M390Y0QY and TKT-01M390Y0S6).
//
// On an iPhone, swiping back left the app, and a riddle that sent the
// player to the drawer for a photo had no way back to it. This drives the
// browser's own Back (what the iOS edge swipe does) through tabs and a
// riddle, then takes a photo from a riddle and checks the player lands
// back on it with the photo selected, ready to submit.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'Back Swipe Hunt' } })).json();
  for (const [i, text] of ['Find the first thing', 'Find the second thing'].entries()) {
    const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
      data: { text, sort_order: i + 1 },
    });
    expect(riddle.status()).toBe(201);
  }
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
});

test.afterAll(async () => {
  await admin?.dispose();
});

test('Back walks the screens, and a photo taken for a riddle comes back selected', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill('Robin');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  const board = page.getByRole('heading', { name: 'Riddle Board' });
  await expect(board).toBeVisible();

  // Board → riddle 2 → Standings; Back twice retraces them.
  await page.getByRole('button', { name: /Find the second thing/ }).click();
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();
  await page.getByRole('link', { name: /Standings/ }).click();
  await expect(page.getByRole('heading', { name: 'Standings' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();
  await page.goBack();
  await expect(board).toBeVisible();
  // Still in the game: Forward works too.
  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();

  // The drawer is empty, so the riddle sends the player to take a photo.
  await page.getByRole('button', { name: /take a photo first/ }).click();
  const backToRiddle = page.getByRole('button', { name: '← Back to Riddle 2' });
  await expect(backToRiddle).toBeVisible();
  await backToRiddle.click();
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();

  // Go again and take the photo: it comes back selected on riddle 2.
  await page.getByRole('button', { name: /take a photo first/ }).click();
  await page.getByLabel('Add a photo').setInputFiles({
    name: 'synthetic.png', mimeType: 'image/png', buffer: PHOTO,
  });
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Evidence photo 1' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Take a new photo' })).toBeVisible();
  await page.getByRole('button', { name: 'Submit to the Batcomputer' }).click();
  await expect(page.getByText('SCANNING', { exact: false }).first()).toBeVisible();

  // The upload carried the riddle's aim tag.
  const drawer = await (await page.request.get('/api/evidence')).json();
  const riddles = (await (await page.request.get('/api/state')).json()).riddles;
  expect(drawer[0].riddle_id).toBe(riddles[1].id);

  // A reload keeps the screen.
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Find the second thing' })).toBeVisible();
});

test('Back from the first screen leaves the game rather than trapping the player', async ({ page }) => {
  await page.goto('/api/health');
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill('Bruce');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/api\/health$/);
});
