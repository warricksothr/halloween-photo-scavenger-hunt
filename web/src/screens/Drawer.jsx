// Drawer screen — the team's pool of candidate photos (increment 5).
//
// Capture is the browser's camera/picker via <input type="file"
// accept="image/*" capture> — design.md's chosen primitive; no camera
// API code of ours to break. Uploads POST multipart through api.js;
// the grid re-reads GET /api/evidence after each upload. Submission of
// a photo to a riddle is increment 6 — until then the drawer is a
// camera roll with a shared destination.
import { useEffect, useRef, useState } from 'preact/hooks';

import { api } from '../api';

export function DrawerScreen({ copy }) {
  const [items, setItems] = useState(null); // null = loading
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef(null);

  async function reload() {
    const result = await api.drawer();
    if (result.error) setError(result.message);
    else setItems(result);
  }

  useEffect(() => {
    reload();
  }, []);

  async function onFileChosen(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    const result = await api.upload(file);
    if (result?.error) setError(result.message);
    await reload();
    setBusy(false);
    // Reset so choosing the same file twice still fires onChange.
    event.target.value = '';
  }

  const c = copy.screens.drawer;

  return (
    <main style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column' }}>
      <h1 class="headline headline-rule" style={{ fontSize: '0.95rem', marginBottom: 12 }}>
        {c.headline}
      </h1>

      {/* The label styles the button; the input does the work. */}
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: 'none' }}
        onChange={onFileChosen}
      />
      <button
        class="btn"
        disabled={busy}
        onClick={() => fileInput.current?.click()}
        style={{ marginBottom: 16 }}
      >
        {busy ? c.uploading : c.capture}
      </button>

      {error && (
        <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
          <div class="verdict-chip">!</div>
          <div><p class="subtext">{error}</p></div>
        </div>
      )}

      {items === null ? (
        <p class="dim">{c.loading}</p>
      ) : items.length === 0 ? (
        <p class="dim">{c.empty}</p>
      ) : (
        <div class="tile-grid" style={{ padding: 0 }}>
          {items.map((item) => (
            // Derivative thumbnails via the authenticated endpoint —
            // never a direct file path (design.md access control).
            <div key={item.id} class="tile" style={{ aspectRatio: '1' }}>
              <img
                src={item.photo_url}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius)' }}
                loading="lazy"
              />
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
