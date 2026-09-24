// One photo serves one riddle (ADR 0035, TKT-01M390Y0TE).
//
// Drew submitted a photo to one riddle and could pick the same photo again
// for a second while the first was still pending. This takes a photo,
// submits it to riddle 1, then opens riddle 2 and checks the photo is shown
// but greyed out and labelled with riddle 1, and that the server refuses it.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

// A 1x1 PNG, the same synthetic photo the other specs upload.
const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'One Photo Hunt' } })).json();
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

test('a photo pending on one riddle is greyed out on another', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill('Robin');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();

  // Take a photo in the drawer, then submit it to riddle 1.
  await page.getByRole('link', { name: /Drawer/ }).click();
  await page.getByLabel('Add a photo').setInputFiles({
    name: 'synthetic.png', mimeType: 'image/png', buffer: PHOTO,
  });
  await expect(page.getByRole('img', { name: 'Your evidence photo' })).toHaveCount(1);
  await page.getByRole('link', { name: /Riddles/ }).click();
  await page.getByRole('button', { name: /Find the first thing/ }).click();
  await page.getByRole('button', { name: 'Evidence photo 1' }).click();
  await page.getByRole('button', { name: 'Submit to the Batcomputer' }).click();
  await expect(page.getByText('SCANNING', { exact: false }).first()).toBeVisible();

  // On riddle 2 the same photo is shown, labelled, and cannot be picked.
  await page.getByRole('button', { name: /Back to the board/ }).click();
  await page.getByRole('button', { name: /Find the second thing/ }).click();
  const taken = page.getByRole('button', { name: 'Evidence photo 1, Scanning · Riddle 1' });
  await expect(taken).toBeDisabled();
  await expect(taken).toContainText('Scanning · Riddle 1');
  await page.screenshot({ path: test.info().outputPath('picker.png') });

  // The server refuses it too, naming the riddle that holds it.
  const csrf = (await page.context().cookies()).find((c) => c.name === 'arkham_csrf').value;
  const riddles = (await (await page.request.get('/api/state')).json()).riddles;
  const drawer = await (await page.request.get('/api/evidence')).json();
  const resp = await page.request.post('/api/submissions', {
    headers: { 'X-CSRF-Token': csrf },
    data: { riddle_id: riddles[1].id, evidence_item_id: drawer[0].id },
  });
  expect(resp.status()).toBe(409);
  expect((await resp.json()).riddle_id).toBe(riddles[0].id);
});
