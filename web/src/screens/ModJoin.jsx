// Moderator join — the mod link's landing surface (increment 7).
//
// Mirrors the player Join screen but simpler: no display name, no
// device label — the server mints the moderator row and labels it.
// The code arrives in the URL (/m/<code>) or is typed.
import { useState } from 'preact/hooks';

import { modJoin } from '../store';

export function ModJoinScreen() {
  const [typedCode, setTypedCode] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // /m/<code> links carry the code in the path, same rule as /j/<code>.
  const pathMatch = window.location.pathname.match(/^\/m\/([A-Za-z0-9]+)/);
  const modCode = pathMatch ? pathMatch[1] : null;

  // The console is a work queue, not the game — plain copy at the call
  // site, no theme pack keys (same rule as conduct surfaces).
  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = await modJoin(modCode ?? typedCode);
    if (result?.error) {
      setError(result.message);
      setBusy(false);
    }
    // Success moves the store to ready/moderator; the shell swaps.
  }

  return (
    <div class="frame">
      <main style={{ flex: 1, padding: '32px 16px' }}>
        <h1 class="headline headline-rule" style={{ marginBottom: 8 }}>Moderator Console</h1>
        <p class="dim" style={{ marginBottom: 24 }}>
          Open the moderator link the host gave you.
        </p>
        <form onSubmit={onSubmit}>
          {!modCode && (
            <div class="field" style={{ marginBottom: 20 }}>
              <label for="mod-code">Moderator code</label>
              <input
                type="text"
                id="mod-code"
                value={typedCode}
                onInput={(e) => setTypedCode(e.target.value.toUpperCase())}
                autocomplete="off"
              />
            </div>
          )}
          {error && (
            <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
              <div class="verdict-chip">!</div>
              <div><p class="subtext">{error}</p></div>
            </div>
          )}
          <button class="btn" type="submit"
                  disabled={busy || (!modCode && !typedCode.trim())}>
            {busy ? 'Opening…' : 'Open the console'}
          </button>
        </form>
      </main>
    </div>
  );
}
