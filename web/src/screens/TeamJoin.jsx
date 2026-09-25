// Team invite landing — /t/<token> (teams stretch).
//
// The screen an invite link opens. Three shapes, mirroring the join
// screen's simplicity:
// - new device: a codename field → redeem mints player + session on
//   the inviter's team and boots straight into the game;
// - existing player on another team with evidence behind them: the
//   switch warning (mocks/team.html) — Stay or Switch team
//   (confirm_switch=true);
// - existing player with no baggage, or a member of the team already:
//   redeems straight through.
//
// The token is a path segment here just like /j/<code> and /m/<code>;
// the SPA fallback in main.py serves this shell for all three.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';
import { InstallHint } from '../components/InstallHint';
import { DEFAULT_THEME, loadTheme } from '../theme';
import { refresh } from '../store';

export function TeamJoinScreen({ token, copy: copyProp }) {
  // copy comes from the store when the player is already logged in;
  // a fresh device renders this before any snapshot, so it loads the
  // arkham pack itself (same pattern as JoinScreen).
  const [loadedCopy, setLoadedCopy] = useState(null);
  const copy = copyProp ?? loadedCopy;
  const [info, setInfo] = useState(null);      // null = loading
  const [loadError, setLoadError] = useState(null);
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirmSwitch, setConfirmSwitch] = useState(false);

  useEffect(() => {
    if (!copyProp) loadTheme(DEFAULT_THEME).then(setLoadedCopy);
  }, [copyProp]);

  useEffect(() => {
    api.inviteInfo(token).then((result) => {
      if (result.error) setLoadError(result.message);
      else setInfo(result);
    });
  }, [token]);

  async function redeem(confirm = false) {
    if (busy) return;
    setBusy(true);
    setError(null);
    const result = await api.redeemInvite(token, name.trim(), '', confirm);
    if (result?.error) {
      if (result.error === 'switch_needs_confirm') {
        // The server found baggage on the current team — show the
        // warning variant and let the player decide.
        setConfirmSwitch(true);
      } else if (result.error === 'team_full') {
        setError(c.full);
      } else if (result.error === 'invite_closed' || result.error === 'bad_invite') {
        setLoadError(c.expired);
      } else if (result.error === 'display_name_required') {
        setError(`${c.nameLabel}?`);
      } else {
        setError(result.message);
      }
    } else {
      // Session cookie is set; boot into the game like any join. The
      // path is cleared first: the token is spent, and the shell's
      // /t/ routing must not send us back here after refresh().
      window.history.replaceState(null, '', '/');
      await refresh();
    }
    setBusy(false);
  }

  // Stay keeps the player's current team, so the invite path has to go:
  // main.jsx routes every /t/<token> back to this screen, and a bare
  // refresh() would only re-render it. Clearing the path lets the
  // snapshot routing put the player back in the game (the same move
  // redeem makes on success).
  async function stay() {
    if (busy) return;
    setBusy(true);
    window.history.replaceState(null, '', '/');
    try {
      await refresh();
    } catch {
      // refresh() folds read failures into the store's error phase and
      // does not reject on them; the store owns the error surface, so
      // this only has to put the warning controls back.
    } finally {
      setBusy(false);
    }
  }

  if (!copy) return <div class="frame" />;
  const c = copy.screens.teamJoin;

  return (
    <div class="frame">
      <main style={{ flex: 1, display: 'grid', placeItems: 'center', padding: 24 }}>
        {/* An invite link opens in Safari on an iPhone; installing first
            and scanning the invite QR in the app keeps the player's
            session in the app (ADR 0043). */}
        <div style={{ maxWidth: 340, width: '100%' }}>
          <InstallHint copy={copy} fromLink />
        </div>
        <div class="panel" style={{ maxWidth: 340, width: '100%' }}>
          {loadError ? (
            <>
              <div class="verdict-chip" style={{ background: 'var(--alert)', color: 'var(--text)' }}>!</div>
              <h1 class="verdict-headline" style={{ color: 'var(--alert)', marginTop: 10 }}>
                {c.unavailable}
              </h1>
              <p class="subtext" style={{ marginTop: 8 }}>{c.expired}</p>
            </>
          ) : info === null ? (
            <p class="dim">{c.loading}</p>
          ) : confirmSwitch ? (
            // Switch warning variant — amber banner, Stay / Switch.
            <div class="verdict-banner sev-amber" style={{ flexDirection: 'column' }}>
              <div style={{ display: 'flex', gap: 12, width: '100%' }}>
                <div class="verdict-chip">!</div>
                <div style={{ flex: 1 }}>
                  <div class="verdict-headline headline-rule">{c.switchHeadline}</div>
                  <p class="subtext" style={{ marginTop: 6 }}>{c.switchBody}</p>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12, width: '100%' }}>
                <button class="btn secondary" style={{ flex: 1 }}
                        disabled={busy}
                        onClick={stay}>
                  {c.stay}
                </button>
                <button class="btn danger" style={{ flex: 1 }}
                        disabled={busy}
                        onClick={() => redeem(true)}>
                  {c.switchConfirm}
                </button>
              </div>
            </div>
          ) : (
            <>
              <h1 class="verdict-headline">{c.headline}</h1>
              <p class="subtext" style={{ marginTop: 8 }}>
                {c.teamLine(info.team_name, info.event_name)}
              </p>
              <div class="field" style={{ marginTop: 14 }}>
                <label for="invite-name">{c.nameLabel}</label>
                <input
                  type="text"
                  id="invite-name"
                  value={name}
                  maxLength={40}
                  onInput={(e) => setName(e.target.value)}
                />
              </div>
              {error && <p class="dim" style={{ color: 'var(--alert)', fontSize: '0.8rem', marginTop: 8 }}>{error}</p>}
              <button class="btn" style={{ marginTop: 14 }}
                      disabled={busy || !name.trim()}
                      onClick={() => redeem(false)}>
                {c.join}
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
