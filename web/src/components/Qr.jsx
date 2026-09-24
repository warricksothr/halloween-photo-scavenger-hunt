// QR code for a join or moderator link (S9CY, ADR 0019, ADR 0026).
//
// The RUNBOOK's setup step is "print two QR codes", so a real generator
// belongs on this screen. Three rules shape it:
//
// - Local rendering only. The venue LAN night may have no route to the
//   internet, so an external chart service (the usual one-line trick) is
//   out; `uqr` is bundled at build time (ADR 0019).
// - Always black on white with a quiet border. A QR that inherits the
//   dark console theme inverts and stops scanning; the palette here is
//   fixed regardless of the page around it.
// - No image loads. The production CSP is `img-src 'self'`, which blocks
//   a data: URI <img>, so the matrix is drawn as inline SVG elements and,
//   for the PNG download, straight onto a canvas (ADR 0026). Only numbers
//   from the matrix reach the markup; the link text never does.
import { encode } from 'uqr';

// Error correction M (15%) survives a smudged print; border is the quiet
// zone, in modules, and is part of the matrix encode returns.
function matrix(text) {
  return encode(text, { ecc: 'M', border: 2 }).data;
}

// One unit square per dark module, in module coordinates.
function modulePath(data) {
  let d = '';
  data.forEach((row, y) => {
    row.forEach((dark, x) => {
      if (dark) d += `M${x} ${y}h1v1h-1z`;
    });
  });
  return d;
}

export function Qr({ text, label, size = 148, class: className = 'admin-qr' }) {
  const data = matrix(text);
  const n = data.length;
  return (
    <svg
      class={className}
      viewBox={`0 0 ${n} ${n}`}
      width={size}
      height={size}
      role="img"
      aria-label={label}
      shape-rendering="crispEdges"
    >
      <rect width={n} height={n} fill="#ffffff" />
      <path d={modulePath(data)} fill="#000000" />
    </svg>
  );
}

// A standalone SVG file for the print shop: vector, so any size is sharp.
export function qrSvgString(text) {
  const data = matrix(text);
  const n = data.length;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n} ${n}"` +
    ` width="1024" height="1024" shape-rendering="crispEdges">` +
    `<rect width="${n}" height="${n}" fill="#ffffff"/>` +
    `<path d="${modulePath(data)}" fill="#000000"/></svg>`
  );
}

// A PNG for slides and chat. Whole pixels per module keep the edges hard,
// so the image is the largest multiple of the module count within `px`.
export function qrPngBlob(text, px = 1024) {
  const data = matrix(text);
  const scale = Math.max(1, Math.floor(px / data.length));
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = data.length * scale;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#000000';
  data.forEach((row, y) => {
    row.forEach((dark, x) => {
      if (dark) ctx.fillRect(x * scale, y * scale, scale, scale);
    });
  });
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

// Save a Blob under a filename. A blob: URL is a download navigation, not
// an image load, so the CSP's img-src does not apply to it.
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoking in the same tick can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
