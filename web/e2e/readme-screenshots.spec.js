import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';

import { expect, test } from '@playwright/test';

const ADMIN_USERNAME = 'browser-test-admin';
const ADMIN_PASSWORD = 'browser-test-only';
const BASE_URL = 'http://127.0.0.1:4173';
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const SCREENSHOT_DIR = process.env.README_SCREENSHOT_DIR ?? path.join(REPO_ROOT, 'docs', 'screenshots');
function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type);
  const length = Buffer.alloc(4);
  const checksum = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])));
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

function makeEvidencePhoto() {
  const width = 320;
  const height = 240;
  const rowSize = width * 3 + 1;
  const pixels = Buffer.alloc(rowSize * height);

  for (let y = 0; y < height; y += 1) {
    const row = y * rowSize;
    pixels[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = row + 1 + x * 3;
      pixels[offset] = 24 + Math.floor((x / width) * 96);
      pixels[offset + 1] = 64 + Math.floor((y / height) * 96);
      pixels[offset + 2] = 128 + Math.floor(((x + y) / (width + height)) * 96);
    }
  }

  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  return Buffer.concat([
    Buffer.from('\x89PNG\r\n\x1a\n', 'binary'),
    pngChunk('IHDR', header),
    pngChunk('IDAT', zlib.deflateSync(pixels)),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

const PHOTO = makeEvidencePhoto();

let codes;
let adminApi;

function screenshotPath(name) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  return path.join(SCREENSHOT_DIR, `${name}.png`);
}

async function normalizeDynamicValues(page) {
  await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const replacements = [
      [/MODERATOR-[A-Z0-9]+/gi, 'MODERATOR'],
      [/\b(?:just now|\d+ min ago)\b/g, 'just now'],
    ];
    let node = walker.nextNode();
    while (node) {
      for (const [pattern, replacement] of replacements) {
        node.textContent = node.textContent.replace(pattern, replacement);
      }
      node = walker.nextNode();
    }
  });
}

async function capture(page, name) {
  await normalizeDynamicValues(page);
  await page.screenshot({ path: screenshotPath(name), fullPage: true });
}

test.beforeAll(async ({ playwright }) => {
  adminApi = await playwright.request.newContext({ baseURL: BASE_URL });

  const login = await adminApi.post('/api/admin/login', {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();

  const eventResponse = await adminApi.post('/api/admin/events', {
    data: { name: 'Arkham Halloween Hunt', leaderboard_visibility: 'live' },
  });
  expect(eventResponse.status()).toBe(201);
  const event = await eventResponse.json();

  const riddles = [
    'Find the Bat-Signal',
    'Locate the hidden gargoyle',
    'Photograph the green question mark',
    'Capture the midnight clock',
    'Find the watchful gargoyle',
    'Spot the silent sentinel',
  ];
  for (const [index, text] of riddles.entries()) {
    const riddleResponse = await adminApi.post(`/api/admin/events/${event.id}/riddles`, {
      data: { text, sort_order: index + 1 },
    });
    expect(riddleResponse.status()).toBe(201);
  }

  const openResponse = await adminApi.post(`/api/admin/events/${event.id}/open`);
  expect(openResponse.ok()).toBeTruthy();
  codes = { join: event.join_code, mod: event.mod_code };
});

test.afterAll(async () => {
  await adminApi?.dispose();
});

test('capture the README product tour', async ({ browser }) => {
  const playerContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
  });
  const moderatorContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const player = await playerContext.newPage();
  const moderator = await moderatorContext.newPage();

  try {
    await player.goto(`/j/${codes.join}`);
    await expect(
      player.getByRole('heading', { name: 'Gotham Needs You' }),
    ).toBeVisible();
    await capture(player, 'join');

    await player.getByLabel('Codename').fill('Batman');
    await player.getByLabel('Device label (optional)').fill("Batman's phone");
    await player.getByRole('button', { name: 'Join the Hunt' }).click();
    await expect(
      player.getByRole('heading', { name: 'Riddle Board' }),
    ).toBeVisible();
    await capture(player, 'riddle-board');

    await player.locator('.tile[title="Find the Bat-Signal"]').click();
    await expect(
      player.getByRole('heading', { name: 'Find the Bat-Signal' }),
    ).toBeVisible();
    await expect(
      player.getByRole('button', { name: /drawer is empty/ }),
    ).toBeVisible();
    await player.getByRole('button', { name: /drawer is empty/ }).click();
    await expect(
      player.getByRole('heading', { name: 'Evidence Drawer' }),
    ).toBeVisible();
    await player.locator('input[type="file"]').setInputFiles({
      name: 'synthetic-evidence.png',
      mimeType: 'image/png',
      buffer: PHOTO,
    });
    await expect(player.locator('main img')).toHaveCount(1);
    await capture(player, 'evidence-drawer');

    await player.getByRole('link', { name: 'Riddles' }).click();
    await player.locator('.tile[title="Find the Bat-Signal"]').click();
    await expect(
      player.getByRole('button', { name: 'Submit to the Batcomputer' }),
    ).toBeVisible();
    await player.locator('main .tile-grid .tile').first().click();
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
    const queueRefresh = moderator.waitForResponse((response) =>
      response.request().method() === 'GET'
      && response.url().endsWith('/api/mod/queue')
      && response.ok(),
    );
    await moderator.getByText('#1 — Batman', { exact: true }).click();
    await expect(
      moderator.getByRole('button', { name: '✓ Riddle Solved' }),
    ).toBeVisible();
    await expect(moderator.getByText('BATMAN — HISTORY')).toBeVisible();
    await queueRefresh;
    await capture(moderator, 'moderator-console');

    await moderator.getByRole('button', { name: '✓ Riddle Solved' }).click();
    await expect(
      moderator.getByText('Queue is clear. Nothing awaiting review.'),
    ).toBeVisible();

    await expect(player.getByText('RIDDLE SOLVED.')).toBeVisible();
    await player.getByRole('button', { name: '← Back to the board' }).click();
    await expect(player.getByText('1/6', { exact: true })).toBeVisible();
    await player.getByRole('link', { name: 'Standings' }).click();
    await expect(
      player.getByRole('heading', { name: 'Standings' }),
    ).toBeVisible();
    const standingsRow = player.locator('.panel .list-row').first();
    await expect(standingsRow).toContainText('Batman');
    await expect(standingsRow).toContainText('1');
    await capture(player, 'standings');
  } finally {
    await Promise.all([playerContext.close(), moderatorContext.close()]);
  }
});
