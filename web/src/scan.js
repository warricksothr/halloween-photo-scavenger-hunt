// Reading a hunt QR code from a photo (ADR 0043, TKT-01M3B0R3QPF5X2QJV0M2174JCW).
//
// On an iPhone a scanned QR or a texted link always opens in Safari, never
// in the installed app, and the app keeps its own sign-in apart from
// Safari's. So the app scans the QR itself: the player takes a photo of it
// and the page decodes it here, on the device.
//
// A still photo rather than a live viewfinder (Drew's call): the file input
// opens the system camera, which needs no camera permission prompt on each
// launch of the installed app, and works the same in every browser.

// The links a hunt QR carries: join (/j/), team invite (/t/) and moderator
// (/m/), each with a code from the server's unambiguous alphabet
// (server/app/ids.py). Case-insensitive, since a code may be retyped.
const HUNT_PATH = /^\/([jtm])\/([A-Za-z0-9]{4,32})\/?$/;

// The in-app path a decoded QR should open, or null when it is not one of
// this site's hunt links. Only the path is kept, so a QR can never send the
// app to another origin or smuggle in a query string: it opens exactly
// what the printed link would.
export function scanTarget(text, origin = window.location.origin) {
  let url;
  try {
    url = new URL(String(text).trim());
  } catch {
    return null;
  }
  if (url.origin !== origin) return null;
  const match = url.pathname.match(HUNT_PATH);
  return match ? `/${match[1]}/${match[2]}` : null;
}

// Sizes to try, longest edge in pixels. A phone photo is 12 megapixels,
// far more than a QR needs and slow to scan; a QR that fills little of the
// frame reads better larger, one that fills it reads fine small.
const SCAN_EDGES = [1024, 1600, 640];

// The text of the first QR code found in an image file, or null. jsQR is
// pure JavaScript (no WebAssembly, which the site's CSP does not allow) and
// is loaded only when a player actually scans.
export async function decodeQrFromFile(file) {
  const { default: jsQR } = await import('jsqr');
  // createImageBitmap reads the file directly: an <img> with a blob: URL
  // would be blocked by the CSP's img-src 'self'. It also applies the
  // photo's EXIF orientation, though a QR reads at any rotation anyway.
  const bitmap = await createImageBitmap(file);
  try {
    for (const edge of SCAN_EDGES) {
      const scale = Math.min(1, edge / Math.max(bitmap.width, bitmap.height));
      const width = Math.max(1, Math.round(bitmap.width * scale));
      const height = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(bitmap, 0, 0, width, height);
      const { data } = ctx.getImageData(0, 0, width, height);
      const found = jsQR(data, width, height, { inversionAttempts: 'attemptBoth' });
      if (found?.data) return found.data;
      if (scale === 1) break; // Already full size; larger tries are the same.
    }
    return null;
  } finally {
    bitmap.close?.();
  }
}
