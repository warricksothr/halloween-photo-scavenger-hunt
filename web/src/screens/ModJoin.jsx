// Moderator join — the mod link's landing surface (increment 7, S9CW).
//
// The link selects the event; the sign-in supplies the person. So the
// screen has three jobs: send the browser to sign in when nobody who may
// moderate is signed in, explain a refused sign-in, and otherwise open the
// console for the code. The code arrives in the URL (/m/<code>) or is
// typed at /mod. The host moderates too (ADR 0027): their admin sign-in
// is enough, so they never see a refusal here.
import { useEffect, useState } from 'preact/hooks';

import { oidcLoginUrl } from '../api';
import { modLinkCode } from '../paths';
import { modJoin } from '../store';
import { DEFAULT_THEME, loadTheme } from '../theme';

// The callback bounces a refused mod-link sign-in back here with a
// marker (api.md). Plain copy at the call site: the console is a work
// queue, not the game, so no theme pack keys.
const REFUSALS = {
  not_authorized: {
    body: 'That sign-in is not a moderator of this event. Use the account the host added to the moderator group.',
  },
};

// Codes are generated upper-case; the server matches exactly. A link
// retyped in lower case, or a code pasted with a stray space, still has
// to reach its event.
function normalise(code) {
  return code.trim().toUpperCase();
}

// Where the SSO round-trip should return, without the refusal marker.
function signInNext() {
  const params = new URLSearchParams(window.location.search);
  params.delete('sso');
  const query = params.toString();
  const path = window.location.pathname;
  return query ? `${path}?${query}` : path;
}

export function ModJoinScreen({ navigate = (url) => window.location.assign(url) }) {
  const [typedCode, setTypedCode] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  // No session means no event theme yet, so the default pack styles the
  // screen, as the player join screen does. Until its stylesheet is in,
  // render the bare frame rather than flash unstyled markup.
  const [styled, setStyled] = useState(false);

  const linkCode = modLinkCode(window.location.pathname);
  const modCode = linkCode ? normalise(linkCode) : null;
  const marker = new URLSearchParams(window.location.search).get('sso');
  const refusal = REFUSALS[marker] ?? null;

  async function attempt(code) {
    setBusy(true);
    setError(null);
    const result = await modJoin(code);
    if (result?.unauthenticated) {
      // No OIDC moderator session: sign in, then the callback returns
      // to this link and the attempt runs again with an identity.
      navigate(oidcLoginUrl(signInNext()));
      return;
    }
    if (result?.error) {
      setError(result.message);
      setBusy(false);
    }
    // Success moves the store to ready/moderator; the shell swaps.
  }

  useEffect(() => {
    // A failed stylesheet load (a stale chunk after a deploy) still shows
    // the screen, unstyled: a moderator who cannot sign in is worse than
    // one who sees plain markup.
    const show = () => setStyled(true);
    loadTheme(DEFAULT_THEME).then(show, show);
  }, []);

  useEffect(() => {
    // A link that carried its code opens straight away for a signed-in
    // moderator. A refusal marker means we just came back from OIDC —
    // do not start another round.
    if (modCode && !refusal) attempt(modCode);
    // Re-run only when the link (or its marker) changes.
    // eslint-disable-next-line
  }, [modCode, marker]);

  if (!styled) return <div class="frame" />;

  if (refusal) {
    return (
      <div class="frame">
        <main style={{ flex: 1, padding: '32px 16px' }}>
          <h1 class="headline headline-rule" style={{ marginBottom: 8 }}>
            Moderator Console
          </h1>
          <div class="verdict-banner sev-red" style={{ marginBottom: 16 }}>
            <div class="verdict-chip">!</div>
            <div>
              <p class="subtext">{refusal.body}</p>
            </div>
          </div>
          <p style={{ marginBottom: 12 }}>
            <a class="admin-btn" href={oidcLoginUrl(signInNext())}>
              Sign in with another account
            </a>
          </p>
        </main>
      </div>
    );
  }

  return (
    <div class="frame">
      <main style={{ flex: 1, padding: '32px 16px' }}>
        <h1 class="headline headline-rule" style={{ marginBottom: 8 }}>
          Moderator Console
        </h1>
        <p class="dim" style={{ marginBottom: 24 }}>
          Open the moderator link the host gave you.
        </p>
        {modCode ? (
          <p class="dim">
            {busy ? 'Opening your console…' : 'Checking your sign-in…'}
          </p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              attempt(normalise(typedCode));
            }}
          >
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
            <button
              class="btn"
              type="submit"
              disabled={busy || !normalise(typedCode)}
            >
              {busy ? 'Opening…' : 'Open the console'}
            </button>
          </form>
        )}
        {error && (
          <div class="verdict-banner sev-red" style={{ marginTop: 16 }}>
            <div class="verdict-chip">!</div>
            <div>
              <p class="subtext">{error}</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
