// QR code for a join or moderator link (S9CY).
//
// The RUNBOOK's setup step is "print two QR codes", so a real generator
// belongs on this screen. Two rules shape it:
//
// - Local rendering only. The venue LAN night may have no route to the
//   internet, so an external chart service (the usual one-line trick) is
//   out; `uqr` is bundled at build time (ADR 0019).
// - Always black on white with a quiet border. A QR that inherits the
//   dark console theme inverts and stops scanning; the palette here is
//   fixed regardless of the page around it.
//
// The SVG goes into an <img> data URI rather than raw markup, so no
// untrusted string ever reaches the DOM as HTML.
import { renderSVG } from 'uqr';

export function Qr({ text, label, size = 148 }) {
  const svg = renderSVG(text, {
    ecc: 'M',
    border: 2,
    pixelSize: 10,
    whiteColor: '#ffffff',
    blackColor: '#000000',
  });
  const src = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  return (
    <img
      class="admin-qr"
      src={src}
      width={size}
      height={size}
      alt={label}
      role="img"
    />
  );
}
