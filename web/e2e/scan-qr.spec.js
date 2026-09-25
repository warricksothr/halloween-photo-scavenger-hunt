// Scanning a hunt QR from a photo (ADR 0043, TKT-01M3B0R3QPF5X2QJV0M2174JCW).
//
// A QR or a link never opens the installed app on an iPhone, so the app's
// join screen has a Scan QR code button: the player photographs the QR and
// the app opens the link it carries. This builds a real QR with the same
// encoder the host console prints with, places it small in a large "photo"
// the way a phone camera would, and scans it through the real decoder.
import { expect, test } from '@playwright/test';
import { encode } from 'uqr';

import { adminApi, loginAdmin } from './support';

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'Scan Hunt' } })).json();
  const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the scanner', sort_order: 1 },
  });
  expect(riddle.status()).toBe(201);
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
});

test.afterAll(async () => {
  await admin?.dispose();
});

// A 2400x1800 JPEG, grey like a room, with the QR for `text` printed on
// white in the middle at about a fifth of the frame.
async function photoOfQr(page, text) {
  const modules = encode(text, { ecc: 'M', border: 4 }).data;
  const bytes = await page.evaluate(async (grid) => {
    const canvas = document.createElement('canvas');
    canvas.width = 2400;
    canvas.height = 1800;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#6b6f75';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const cell = Math.floor(480 / grid.length);
    const size = cell * grid.length;
    const x0 = (canvas.width - size) / 2;
    const y0 = (canvas.height - size) / 2;
    ctx.fillStyle = '#fff';
    ctx.fillRect(x0, y0, size, size);
    ctx.fillStyle = '#000';
    grid.forEach((row, y) => row.forEach((dark, x) => {
      if (dark) ctx.fillRect(x0 + x * cell, y0 + y * cell, cell, cell);
    }));
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85));
    return Array.from(new Uint8Array(await blob.arrayBuffer()));
  }, modules);
  return { name: 'qr.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(bytes) };
}

test('a photo of the join QR opens that game\'s join page', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const scan = page.getByRole('button', { name: 'Scan QR code' });
  await expect(scan).toBeVisible();

  const origin = new URL(baseURL).origin;
  await page.getByLabel('Scan QR code').setInputFiles(
    await photoOfQr(page, `${origin}/j/${event.join_code}`),
  );

  await page.waitForURL(`**/j/${event.join_code}`);
  // The code came from the QR, so the form asks only for a codename.
  await expect(page.getByLabel('Join code')).toHaveCount(0);
  await page.getByLabel('Codename').fill('Scanner');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();
});

test('a QR for somewhere else is refused and not followed', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Scan QR code').setInputFiles(
    await photoOfQr(page, 'https://elsewhere.example/j/ABCD234567'),
  );
  await expect(page.getByRole('alert')).toContainText('not a link for this hunt');
  expect(new URL(page.url()).pathname).toBe('/');
});
