// The Scan QR code button (ADR 0043). It opens the camera for a still
// photo, reads the QR in it, and opens the link the QR carries, exactly as
// following the link would have. Anything that is not one of this site's
// join, invite or moderator links is refused and never opened.
import { useRef, useState } from 'preact/hooks';

import { decodeQrFromFile, scanTarget } from '../scan';

export function ScanQr({
  copy,
  decode = decodeQrFromFile,
  navigate = (path) => window.location.assign(path),
}) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const c = copy.screens.join.scan;

  async function onPhoto(event) {
    const file = event.target.files?.[0];
    // Clear the input so the same photo can be picked again after a miss.
    event.target.value = '';
    if (!file) return;
    setBusy(true);
    setError(null);
    let text = null;
    try {
      text = await decode(file);
    } catch {
      // An image the browser cannot open reads as "no code found".
    }
    const target = text ? scanTarget(text) : null;
    if (target) {
      // A full navigation, as the link itself would be: the shell routes
      // /j/, /t/ and /m/ on load, and stays inside the installed app.
      navigate(target);
      return;
    }
    setError(text ? c.notOurs : c.notFound);
    setBusy(false);
  }

  return (
    <div class="scan-qr">
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        aria-label={c.button}
        style={{ display: 'none' }}
        onChange={onPhoto}
      />
      <button type="button" class="btn secondary" disabled={busy}
              onClick={() => input.current?.click()}>
        {busy ? c.reading : c.button}
      </button>
      <p class="dim" style={{ marginTop: 8 }}>{c.hint}</p>
      {error && (
        <div class="verdict-banner sev-red" role="alert" style={{ marginTop: 12 }}>
          <div class="verdict-chip">!</div>
          <div><p class="subtext">{error}</p></div>
        </div>
      )}
    </div>
  );
}
