// Drawer screen — the team's pool of candidate photos (increment 5).
//
// Capture is the browser's camera/picker via <input type="file"
// accept="image/*" capture> — design.md's chosen primitive; no camera
// API code of ours to break. Uploads POST multipart through api.js;
// the grid re-reads GET /api/evidence after each upload.
//
// Increment 8: when the snapshot's restriction.level ≥ 2 (cooldown or
// ban), the capture button is replaced by the upload-suspended variant
// (mocks/drawer.html). Copy is plain — conduct surfaces are un-themed.
import { useEffect, useRef, useState } from 'preact/hooks';

import { api } from '../api';

// Opened from a riddle (returnTo), the drawer tags the upload with that
// riddle and, once it is saved, goes back to the riddle with the photo
// selected (ADR 0036). onReturn is the same Back as the browser's.
export function DrawerScreen({ snapshot, copy, returnTo = null, onReturn, onUploadedFor }) {
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
    const result = await api.upload(file, returnTo ?? undefined);
    // Reset so choosing the same file twice still fires onChange.
    event.target.value = '';
    if (!result?.error && returnTo) {
      onUploadedFor(result.id);
      return;
    }
    if (result?.error) setError(result.message);
    await reload();
    setBusy(false);
  }

  const c = copy.screens.drawer;
  const returnNumber = returnTo
    ? (snapshot?.riddles ?? []).findIndex((r) => r.id === returnTo) + 1
    : 0;
  const restriction = snapshot?.me?.restriction;
  const uploadsSuspended = (restriction?.level ?? 0) >= 2;
  // Strike 2 names its window; strike 3 is for the rest of the event.
  const suspendedUntil =
    restriction?.level === 2 && restriction.cooldown_until
      ? new Date(restriction.cooldown_until * 1000).toLocaleTimeString()
      : null;

  return (
    <main style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column' }}>
      {returnNumber > 0 && (
        <button
          class="btn secondary"
          onClick={onReturn}
          style={{ width: 'auto', padding: '8px 14px', marginBottom: 12, alignSelf: 'flex-start' }}
        >
          {c.backToRiddle(returnNumber)}
        </button>
      )}
      <h1 class="headline headline-rule" style={{ fontSize: '0.95rem', marginBottom: 12 }}>
        {c.headline}
      </h1>
      {returnNumber > 0 && <p class="dim" style={{ marginBottom: 12 }}>{c.forRiddle(returnNumber)}</p>}

      {uploadsSuspended ? (
        <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
          <div class="verdict-chip" style={{ background: 'var(--alert)', color: 'var(--text)' }}>!</div>
          <div>
            <div class="verdict-headline">Uploads Suspended</div>
            <p class="subtext" style={{ marginTop: 6 }}>
              A moderator removed one of your photos for violating the event
              rules. Uploads are disabled{suspendedUntil
                ? <> until <b>{suspendedUntil}</b></>
                : <> for the rest of this event</>}.
              You can still view the board and your existing photos.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* The label styles the button; the input does the work. */}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            aria-label={c.addLabel}
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
        </>
      )}

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
                alt={c.photoAlt}
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
