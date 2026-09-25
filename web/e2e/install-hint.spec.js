// The install suggestion on an iPhone (TKT-01M390Y0VQ).
//
// Safari never offers to install a web app, and the installed app keeps its
// own storage apart from Safari's, so a player who installs after joining
// has to join again. The join screen therefore suggests installing first,
// then scanning the QR again in the app, or entering the join code (ADR
// 0043). This runs the join screen as an iPhone, and checks the icons iOS
// and Android install from are served.
import { expect, test } from '@playwright/test';

import { adminApi, loginAdmin } from './support';

const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';

let admin;
let event;

test.beforeAll(async ({ playwright }) => {
  admin = await adminApi(playwright);
  await loginAdmin(admin);
  event = await (await admin.post('/api/admin/events', { data: { name: 'Install Hunt' } })).json();
  // An event opens only with a riddle on the board.
  const riddle = await admin.post(`/api/admin/events/${event.id}/riddles`, {
    data: { text: 'Find the thing', sort_order: 1 },
  });
  expect(riddle.status()).toBe(201);
  expect((await admin.post(`/api/admin/events/${event.id}/open`)).ok()).toBeTruthy();
});

test.afterAll(async () => {
  await admin?.dispose();
});

test.describe('on an iPhone', () => {
  test.use({ userAgent: IPHONE, viewport: { width: 390, height: 844 } });

  test('the join screen suggests installing first, with the code to use', async ({ page }) => {
    await page.goto(`/j/${event.join_code}`);
    const hint = page.getByRole('region', { name: 'Install the Batcomputer' });
    await expect(hint).toContainText('Add to Home Screen');
    await expect(hint).toContainText('tap Scan QR code and scan the QR again');
    await expect(hint).toContainText(`or enter code ${event.join_code}`);

    // Not now hides it on this page. The plain join page keeps it hidden,
    // but a link with a code brings it back: joining in Safari there
    // would strand the player outside the app (ADR 0043).
    await hint.getByRole('button', { name: 'Not now' }).click();
    await expect(hint).toHaveCount(0);
    await page.goto('/');
    await expect(page.getByLabel('Codename')).toBeVisible();
    await expect(hint).toHaveCount(0);
    await page.goto(`/j/${event.join_code}`);
    await expect(hint).toBeVisible();
  });

  test('an invite link brings the suggestion back too (ADR 0043)', async ({ page, playwright }) => {
    // A team with room for two, and an invite minted by its first member.
    const teamEvent = await (await admin.post('/api/admin/events', {
      data: { name: 'Invite Install Hunt', team_size_limit: 4 },
    })).json();
    await admin.post(`/api/admin/events/${teamEvent.id}/riddles`, {
      data: { text: 'Find the team', sort_order: 1 },
    });
    expect((await admin.post(`/api/admin/events/${teamEvent.id}/open`)).ok()).toBeTruthy();
    const inviter = await adminApi(playwright);
    try {
      const joined = await inviter.post(`/api/join/${teamEvent.join_code}`, {
        data: { display_name: 'Inviter' },
      });
      expect(joined.status()).toBe(201);
      const invite = await (await inviter.post('/api/team/invites')).json();

      // Dismissed earlier on the plain join page...
      await page.goto('/');
      const hint = page.getByRole('region', { name: 'Install the Batcomputer' });
      await hint.getByRole('button', { name: 'Not now' }).click();
      await expect(hint).toHaveCount(0);

      // ...and shown again on the invite page, where "Not now" hides it
      // for that page.
      await page.goto(invite.invite_url);
      await expect(hint).toContainText('tap Scan QR code and scan the QR again');
      await hint.getByRole('button', { name: 'Not now' }).click();
      await expect(hint).toHaveCount(0);
    } finally {
      await inviter.dispose();
    }
  });
});

test('a desktop browser without an install prompt sees no hint', async ({ page }) => {
  await page.goto(`/j/${event.join_code}`);
  await expect(page.getByLabel('Codename')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Install the Batcomputer' })).toHaveCount(0);
});

test('the home-screen icons are served as PNGs', async ({ request }) => {
  const html = await (await request.get('/')).text();
  expect(html).toContain('rel="apple-touch-icon" href="/icons/apple-touch-icon.png"');
  const manifest = await (await request.get('/manifest.webmanifest')).json();
  const sizes = manifest.icons.filter((i) => i.type === 'image/png').map((i) => i.sizes);
  expect(sizes).toEqual(['192x192', '512x512']);
  for (const path of ['/icons/apple-touch-icon.png', '/icons/icon-192.png', '/icons/icon-512.png']) {
    const resp = await request.get(path);
    expect(resp.status()).toBe(200);
    expect(resp.headers()['content-type']).toBe('image/png');
  }
});
