// The admin console at phone width (TKT-01M3AFZWB4RERA95SKVN0QVA6F).
//
// The console was laid out for a laptop, and on a phone the event picker
// pushed every panel past the screen while riddle and event rows squeezed
// their text beside the buttons. This drives each tab at 390px with a long
// event name and measures: no horizontal overflow, and each row's controls
// sit under its content. At 1280px the rows keep their controls beside the
// content, so the laptop layout is pinned too. Two players share a codename
// here, so the host's picker labels are checked in the same pass
// (TKT-01M3AFZWA1GWCGPTZ4G6RW3MXS).
import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USERNAME, adminApi, loginAdmin } from './support';

const EVENT_NAME = "The Riddler's Halloween — A Deliberately Long Demo Event Name";
const RIDDLE =
  'Every face in this city wears one, and nobody reads it aloud. Bring me one long enough to need four of your digits.';

let admin;

test.beforeAll(async ({ playwright, browser }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  const event = await (
    await admin.post('/api/admin/events', { data: { name: EVENT_NAME } })
  ).json();
  for (let i = 1; i <= 3; i += 1) {
    const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
      data: { text: RIDDLE, sort_order: i },
    });
    expect(riddle.status()).toBe(201);
  }
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();

  // Two guests who both picked Robin.
  for (const device of ['Front door phone', 'Kitchen tablet']) {
    const guest = await browser.newContext();
    const page = await guest.newPage();
    await page.goto(`/j/${event.join_code}`);
    await page.getByLabel('Codename').fill('Robin');
    await page.getByLabel(/Device label/).fill(device);
    await page.getByRole('button', { name: 'Join the Hunt' }).click();
    await expect(page.getByTestId('app-frame')).toBeVisible();
    await guest.close();
  }
});

test.afterAll(async () => {
  await admin?.dispose();
});

// Sign the page's own context in, so the console renders signed in.
async function signIn(page) {
  await page.goto('/api/health');
  const csrf = (await page.context().cookies()).find((c) => c.name === 'arkham_csrf').value;
  const login = await page.request.post('/api/admin/login', {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
    headers: { 'X-CSRF-Token': csrf },
  });
  expect(login.ok()).toBeTruthy();
}

async function horizontalOverflow(page) {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

async function openTab(page, name) {
  await page.locator('.admin-tab', { hasText: name }).click();
}

// Whether a row's controls start below its content rather than beside it.
async function controlsBelow(page, row, content) {
  const rowLocator = page.locator(row).first();
  const text = await rowLocator.locator(content).first().boundingBox();
  const actions = await rowLocator.locator(':scope > .admin-actions, :scope > .admin-row > .admin-actions').first().boundingBox();
  return actions.y >= text.y + text.height - 1;
}

test('every admin tab fits a phone, with controls under their content', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto('/admin');

  await expect(page.getByRole('button', { name: 'Links & QR' }).first()).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
  expect(await controlsBelow(page, '.admin-event', '.admin-event-name')).toBe(true);

  await openTab(page, 'Riddles');
  await expect(page.getByRole('button', { name: 'Edit' }).first()).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
  expect(await controlsBelow(page, '.admin-riddle', '.admin-riddle-body')).toBe(true);

  await page.getByRole('button', { name: 'Edit' }).first().click();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
  await page.getByRole('button', { name: 'Cancel' }).click();

  await openTab(page, 'Host actions');
  const picker = page.getByLabel('Player');
  await expect(picker).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);

  const labels = await picker.locator('option').allInnerTexts();
  expect(labels).toHaveLength(2);
  expect(new Set(labels).size).toBe(2);
  expect(labels[0]).toMatch(/^Robin · joined .+ · Front door phone$/);
  expect(labels[1]).toMatch(/^Robin · joined .+ · Kitchen tablet$/);
});

test('the laptop layout keeps controls beside their content', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page);
  await page.goto('/admin');

  await expect(page.getByRole('button', { name: 'Links & QR' }).first()).toBeVisible();
  expect(await controlsBelow(page, '.admin-event', '.admin-event-name')).toBe(false);

  await openTab(page, 'Riddles');
  await expect(page.getByRole('button', { name: 'Edit' }).first()).toBeVisible();
  expect(await controlsBelow(page, '.admin-riddle', '.admin-riddle-body')).toBe(false);
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
});
