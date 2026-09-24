// Render public/icons/icon.svg to the PNG icons a phone installs from.
//
// iOS ignores SVG and manifest icons for the home screen and wants a
// 180x180 apple-touch-icon PNG; without one it uses a page snapshot.
// Android's install prompt wants 192 and 512 PNGs in the manifest. The
// SVG stays the one source: rerun `node scripts/render-icons.mjs` after
// changing it and commit the PNGs.
//
// Each PNG is square with the icon's background colour to the edges.
// iOS masks its own rounded corners and fills anything transparent with
// black, so the SVG's rounded corners must not leave transparent pixels.
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

const ICONS = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'public', 'icons');
const SIZES = [
  ['apple-touch-icon.png', 180],
  ['icon-192.png', 192],
  ['icon-512.png', 512],
];

const svg = await readFile(path.join(ICONS, 'icon.svg'), 'utf8');
const browser = await chromium.launch();
try {
  for (const [name, size] of SIZES) {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    await page.setContent(
      `<html><body style="margin:0;background:#0a0e14">
         <div style="width:${size}px;height:${size}px">${svg.replace('<svg ', `<svg width="${size}" height="${size}" `)}</div>
       </body></html>`,
    );
    await page.screenshot({ path: path.join(ICONS, name), omitBackground: false });
    await page.close();
    console.log(`wrote icons/${name} (${size}x${size})`);
  }
} finally {
  await browser.close();
}
