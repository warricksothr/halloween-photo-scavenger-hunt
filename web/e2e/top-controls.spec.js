// The header and tabs stay on screen while a long board scrolls (ADR 0034,
// TKT-01M390Y0PN10W11HEB6FM91PZ6).
//
// On an iPhone the tab bar used to sit after all the content, and the
// header with Switch Case scrolled away above it, so every tab change
// began with a scroll. This fills a board past the fold at 390x844,
// scrolls to the end, and checks the pinned bar is still in view and
// usable, without covering the start of the screen or overflowing.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'Long Night Hunt' } })).json();
  for (let i = 1; i <= 30; i += 1) {
    const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
      data: { text: `Riddle number ${i}: find the thing that answers it`, sort_order: i },
    });
    expect(riddle.status()).toBe(201);
  }
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
});

test.afterAll(async () => {
  await admin?.dispose();
});

// Whether the element lies wholly inside the viewport.
async function inView(page, locator) {
  const box = await locator.boundingBox();
  const { height } = page.viewportSize();
  return box !== null && box.y >= 0 && box.y + box.height <= height;
}

async function horizontalOverflow(page) {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test('the header and tabs stay pinned at the top of a long board', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/j/${event.join_code}`);
  await page.getByLabel('Codename').fill('Robin');
  await page.getByRole('button', { name: 'Join the Hunt' }).click();
  await expect(page.getByRole('heading', { name: 'Riddle Board' })).toBeVisible();

  const bar = page.locator('.top-bar');
  const switchCase = page.getByRole('button', { name: 'Switch Case' });
  const standings = page.getByRole('link', { name: /Standings/ });

  // The bar starts at the top, and the board's heading starts below it.
  const barBox = await bar.boundingBox();
  expect(barBox.y).toBe(0);
  const heading = await page.getByRole('heading', { name: 'Riddle Board' }).boundingBox();
  expect(heading.y).toBeGreaterThanOrEqual(barBox.y + barBox.height - 1);

  // The board is long enough to scroll; at its end the controls are still
  // in view, and the bar has not moved.
  const scrollable = await page.evaluate(
    () => document.documentElement.scrollHeight - window.innerHeight,
  );
  expect(scrollable).toBeGreaterThan(200);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(200);
  expect(await inView(page, switchCase)).toBe(true);
  expect(await inView(page, standings)).toBe(true);
  expect((await bar.boundingBox()).y).toBe(0);
  // Measured on the board itself, the screen this spec fills past the fold.
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);

  // A tab works from there without scrolling back.
  await standings.click();
  await expect(standings).toHaveAttribute('aria-current', 'page');
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(1);
});
