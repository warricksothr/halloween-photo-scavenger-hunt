// Players see a pending or flagged photo only as its blurhash (ADR 0040,
// TKT-01M3AMNFH).
//
// This takes a photo for a riddle and submits it, then checks the Drawer
// tab paints the photo's blurhash on a canvas instead of showing it while it
// scans. A moderator then flags it inappropriate, and the drawer keeps only
// the blur, marked as removed, while the photo itself stays out of reach.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

// A 64x48 PNG, two colour halves, so the blurhash has something to show.
async function twoTonePng(page) {
  return page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 48;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#c82828';
    ctx.fillRect(0, 0, 32, 48);
    ctx.fillStyle = '#143cc8';
    ctx.fillRect(32, 0, 32, 48);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    return Array.from(new Uint8Array(await blob.arrayBuffer()));
  });
}

// Whether a canvas has been painted (any non-transparent pixel).
async function painted(locator) {
  return locator.evaluate((canvas) => {
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < data.length; i += 4) if (data[i] > 0) return true;
    return false;
  });
}

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'Blur Hunt' } })).json();
  const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the two-tone thing', sort_order: 1 },
  });
  expect(riddle.status()).toBe(201);
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
});

test.afterAll(async () => {
  await admin?.dispose();
});

test('a scanning photo is a blur, and a removed one stays only a blur', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill('Robin');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();

  // Take a photo for the riddle; it comes back selected, and is submitted.
  await page.getByRole('button', { name: /Find the two-tone thing/ }).click();
  await page.getByRole('button', { name: /take a photo first/ }).click();
  await page.getByLabel('Add a photo').setInputFiles({
    name: 'two-tone.png', mimeType: 'image/png', buffer: Buffer.from(await twoTonePng(page)),
  });
  await page.getByRole('button', { name: 'Submit to the Batcomputer' }).click();
  await expect(page.getByText('SCANNING', { exact: false }).first()).toBeVisible();
  // The banner shows the photo blurred behind it.
  await expect(page.locator('canvas.banner-blurhash')).toHaveCount(1);

  // The Drawer tab: a painted blur, no photo.
  await page.getByRole('link', { name: /Drawer/ }).click();
  const blur = page.getByRole('img', { name: 'Your photo, blurred while it is scanned' });
  await expect(blur).toBeVisible();
  expect(await painted(blur)).toBe(true);
  await expect(page.getByText('Scanning · Riddle 1')).toBeVisible();
  await expect(page.getByRole('img', { name: 'Your evidence photo' })).toHaveCount(0);

  // A moderator flags it.
  const state = await (await page.request.get('/api/state')).json();
  const drawer = await (await page.request.get('/api/evidence')).json();
  expect((await admin.post(`/api/mod/join/${event.mod_code}`)).status()).toBe(201);
  const flagged = await admin.post(`/api/mod/queue/${state.submissions[0].id}/inappropriate`, {
    data: { note: 'test flag' },
  });
  expect(flagged.ok()).toBeTruthy();

  // The drawer keeps the blur, marked removed; the photo is out of reach.
  await page.reload();
  const acknowledge = page.getByRole('button', { name: 'I understand' });
  if (await acknowledge.isVisible()) await acknowledge.click();
  await page.getByRole('link', { name: /Drawer/ }).click();
  const removed = page.getByRole('img', { name: 'A removed photo, shown blurred' });
  await expect(removed).toBeVisible();
  expect(await painted(removed)).toBe(true);
  await expect(page.getByText('Photo removed')).toBeVisible();
  const after = await (await page.request.get('/api/evidence')).json();
  expect(after[0]).toMatchObject({ id: drawer[0].id, quarantined: true, photo_url: null });
  expect((await page.request.get(`/api/evidence/${drawer[0].id}/photo`)).status()).toBe(404);
});
