// Switching games and signing out on a phone (ADR 0033).
//
// A player in one hunt needs to reach the landing page to pick another,
// without losing the first: Switch Case ends the session but keeps the game
// in Open Cases. Signing out on the Team tab is for a phone changing hands,
// so it forgets the game on this device.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

let admin;
const games = {};

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  for (const name of ['Gotham Night Hunt', 'Blackgate Breakout']) {
    const event = await (await admin.post('/api/admin/events', { data: { name } })).json();
    const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
      data: { text: 'Find the thing', sort_order: 1 },
    });
    expect(riddle.status()).toBe(201);
    expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
    games[name] = event;
  }
});

test.afterAll(async () => {
  await admin?.dispose();
});

async function join(page, event, codename) {
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill(codename);
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();
}

test('Switch Case keeps each game one tap away; signing out forgets one', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await join(page, games['Gotham Night Hunt'], 'Robin');

  // The header fits the phone with the control in it.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  // Switch to the landing page, where the first game is still listed, and
  // join a second one.
  await page.getByRole('button', { name: 'Switch Case' }).click();
  const cases = page.getByRole('region', { name: 'Open Cases' });
  await expect(cases).toContainText('Gotham Night Hunt');
  await expect(page).toHaveURL(/\/$/);
  await join(page, games['Blackgate Breakout'], 'Bruce');

  // Both listed after switching again; tap back into the first as Robin.
  await page.getByRole('button', { name: 'Switch Case' }).click();
  await expect(cases).toContainText('Return as Robin');
  await expect(cases).toContainText('Return as Bruce');
  await cases.getByRole('button', { name: /Gotham Night Hunt/ }).click();
  await expect(page.locator('header')).toContainText('Robin');

  // Sign out of this phone from the Team tab: it asks first, then forgets
  // Gotham here while Blackgate stays listed.
  await page.getByRole('link', { name: /Team/ }).click();
  await page.getByRole('button', { name: 'Sign out of this phone' }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(cases).toContainText('Return as Bruce');
  await expect(cases).not.toContainText('Gotham Night Hunt');
});
