// Admin console shell (S9CX).
//
// Self-contained on purpose: it talks to the admin API directly and never
// touches the player store or the theme pack. The host console is a
// laptop-first tool, so it carries its own plain frame (admin.css) instead
// of the Arkham phone shell — a new theme must not restyle the host's
// controls, and the console must not depend on a theme being loaded.
//
// Session bootstrap: GET /api/admin/events is the probe. A 401 means no
// admin session (show login); a 200 list is both proof of session and the
// console's first data. The admin cookie is httpOnly, so the client cannot
// read it — a probe is the only honest way to know, and the server is the
// only authority (the client role stays cosmetic).
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';
import { AdminEvents } from './AdminEvents';
import { AdminRiddles } from './AdminRiddles';
import '../admin.css';

const NAV = [
  { key: 'events', label: 'Events' },
  { key: 'riddles', label: 'Riddles' },
  { key: 'host', label: 'Host actions' },
];

export function AdminScreen() {
  // probing | login | console | error
  const [phase, setPhase] = useState('probing');
  const [events, setEvents] = useState([]);
  const [probeError, setProbeError] = useState(null);
  const [tab, setTab] = useState('events');

  async function probe() {
    setPhase('probing');
    setProbeError(null);
    const result = await api.adminEvents();
    if (result?.unauthenticated) {
      setPhase('login');
      return;
    }
    if (result?.error) {
      // A 5xx or a dropped connection is not "signed out" — the host gets
      // a retry instead of a login form that would also fail.
      setProbeError(result.message);
      setPhase('error');
      return;
    }
    setEvents(result);
    setPhase('console');
  }

  useEffect(() => {
    probe();
  }, []);

  if (phase === 'probing') {
    return <Shell><p class="admin-dim">Checking the host session…</p></Shell>;
  }

  if (phase === 'error') {
    return (
      <Shell>
        <div class="admin-error">{probeError}</div>
        <button class="admin-btn" onClick={probe}>Try again</button>
      </Shell>
    );
  }

  if (phase === 'login') {
    return <AdminLogin onSignedIn={probe} />;
  }

  return (
    <Shell signedIn>
      <nav class="admin-nav">
        {NAV.map((item) => (
          <button
            key={item.key}
            class="admin-tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      {tab === 'events' && <AdminEvents initialEvents={events} />}
      {tab === 'riddles' && <AdminRiddles />}
      {tab === 'host' && (
        <div class="admin-panel">
          <p>Host actions — strike reversal and player history — arrive next.</p>
          <p class="admin-note">
            The round lifecycle (open, close, purge) is on the events panel.
          </p>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children, signedIn = false }) {
  return (
    <div class="admin-shell">
      <header class="admin-header">
        <h1>Arkham Hunt — Host Console</h1>
        <span class="admin-dim">/admin</span>
        <span class="admin-spacer" />
        {signedIn && (
          <button class="admin-btn secondary" onClick={signOut}>Sign out</button>
        )}
      </header>
      <main class="admin-main">{children}</main>
    </div>
  );
}

async function signOut() {
  await api.adminLogout();
  // A reload is the honest reset: it drops the OIDC identity cookie and
  // re-runs the probe, so the shell cannot keep showing a stale console.
  window.location.assign('/admin');
}

function AdminLogin({ onSignedIn }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    const result = await api.adminLogin(username, password);
    if (result?.error) {
      setError(result.message);
      setBusy(false);
      return;
    }
    setBusy(false);
    await onSignedIn();
  }

  return (
    <Shell>
      <div class="admin-login">
        <h2>Sign in</h2>
        <p class="admin-note" style={{ marginBottom: 16 }}>
          Host access only. Moderators use the moderator link from the event.
        </p>
        {/* Top-level navigation, not fetch: the server decides where the
            OIDC flow goes, and an unconfigured provider answers with a
            real 503 message the host can read. */}
        <a class="admin-btn" href="/api/auth/oidc/login?next=%2Fadmin">
          Sign in with Authentik
        </a>
        <p class="admin-note" style={{ marginBottom: 24 }}>
          If single sign-on is not configured here, use the password below.
        </p>
        <form onSubmit={onSubmit}>
          {error && <div class="admin-error">{error}</div>}
          <div class="admin-field">
            <label for="admin-username">Username</label>
            <input
              class="admin-input"
              id="admin-username"
              type="text"
              value={username}
              autocomplete="username"
              onInput={(e) => setUsername(e.target.value)}
            />
          </div>
          <div class="admin-field">
            <label for="admin-password">Password</label>
            <input
              class="admin-input"
              id="admin-password"
              type="password"
              value={password}
              autocomplete="current-password"
              onInput={(e) => setPassword(e.target.value)}
            />
          </div>
          <button
            class="admin-btn"
            type="submit"
            disabled={busy || !username || !password}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </Shell>
  );
}
