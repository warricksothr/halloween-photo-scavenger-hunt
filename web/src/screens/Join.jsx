// Join screen — the only unauthenticated surface.
//
// The join code arrives in the URL (/j/<code> from the QR) or is typed
// from the projected fallback. The screen renders before any snapshot
// exists, so its copy comes from the arkham pack by default — a player
// hasn't joined an event yet, so there is no event theme to honor.
//
// Above the form it lists the live games this device already joined
// (ADR 0031): a session ends after 12 hours, and a fresh join would be a
// new player with an empty drawer, so rejoining is one tap instead.
import { useEffect, useState } from 'preact/hooks';

import { join, resumableGames, resume } from '../store';
import { DEFAULT_THEME, loadTheme } from '../theme';

export function JoinScreen() {
  const [copy, setCopy] = useState(null);
  const [displayName, setDisplayName] = useState('');
  const [deviceLabel, setDeviceLabel] = useState('');
  const [typedCode, setTypedCode] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [games, setGames] = useState([]);
  const [resumeError, setResumeError] = useState(null);

  // All hooks must run before any early return (hook order is fixed),
  // so the theme loads in an effect and the loading gate sits below.
  useEffect(() => {
    loadTheme(DEFAULT_THEME).then(setCopy);
    resumableGames().then(setGames);
  }, []);

  // /j/<code> links put the code in the path; everything else types it.
  const pathMatch = window.location.pathname.match(/^\/j\/([A-Za-z0-9]+)/);
  const joinCode = pathMatch ? pathMatch[1] : null;

  if (!copy) return <div class="frame" />;

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = await join(joinCode ?? typedCode, displayName, deviceLabel);
    if (result?.error) {
      setError(result.message);
      setBusy(false);
    }
    // Success moves the store to 'ready'; the shell swaps screens.
  }

  async function onResume(game) {
    setBusy(true);
    setResumeError(null);
    const result = await resume(game.event_id);
    if (result?.error) {
      // The game closed or refused since the list loaded: say why, and
      // drop it so the list only offers what can still be rejoined.
      setResumeError(result.message);
      setGames((current) => current.filter((g) => g.event_id !== game.event_id));
      setBusy(false);
    }
    // Success moves the store to 'ready'; the shell swaps screens.
  }

  const c = copy.screens.join;

  return (
    <div class="frame">
      <main style={{ flex: 1, padding: '32px 16px' }}>
        <h1 class="headline headline-rule" style={{ marginBottom: 8 }}>{c.headline}</h1>
        <p class="dim" style={{ marginBottom: 24 }}>{c.subtext}</p>

        {games.length > 0 && (
          <section aria-labelledby="resume-heading" style={{ marginBottom: 24 }}>
            <h2 id="resume-heading" class="headline" style={{ fontSize: '1rem', marginBottom: 8 }}>
              {c.resumeHeading}
            </h2>
            <div class="panel" style={{ padding: '0 16px' }}>
              {games.map((game) => (
                <button
                  key={game.event_id}
                  type="button"
                  class="list-row"
                  disabled={busy}
                  onClick={() => onResume(game)}
                >
                  <span style={{ flex: 1 }}>{game.event_name}</span>
                  <span class="dim">{c.resumeAs(game.display_name)}</span>
                </button>
              ))}
            </div>
            <p class="dim" style={{ marginTop: 16 }}>{c.resumeOr}</p>
          </section>
        )}

        {resumeError && (
          <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
            <div class="verdict-chip">!</div>
            <div><p class="subtext">{resumeError}</p></div>
          </div>
        )}

        <form onSubmit={onSubmit}>
          {!joinCode && (
            <div class="field" style={{ marginBottom: 16 }}>
              <label for="join-code">{c.codeLabel}</label>
              <input
                type="text"
                id="join-code"
                value={typedCode}
                onInput={(e) => setTypedCode(e.target.value.toUpperCase())}
                placeholder={c.codePlaceholder}
                autocomplete="off"
              />
            </div>
          )}
          <div class="field" style={{ marginBottom: 16 }}>
            <label for="display-name">{c.nameLabel}</label>
            <input
              type="text"
              id="display-name"
              value={displayName}
              onInput={(e) => setDisplayName(e.target.value)}
              maxLength={40}
              required
            />
          </div>
          <div class="field" style={{ marginBottom: 20 }}>
            <label for="device-label">{c.deviceLabel}</label>
            <input
              type="text"
              id="device-label"
              value={deviceLabel}
              onInput={(e) => setDeviceLabel(e.target.value)}
              maxLength={80}
              placeholder={c.devicePlaceholder}
            />
          </div>
          {error && (
            <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
              <div class="verdict-chip">!</div>
              <div><p class="subtext">{error}</p></div>
            </div>
          )}
          <button class="btn" type="submit"
                  disabled={busy || !displayName.trim() || (!joinCode && !typedCode.trim())}>
            {c.submit}
          </button>
        </form>
      </main>
    </div>
  );
}
