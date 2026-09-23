import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';

import { initErrorReporting } from './errors';
import { getState, refresh, retry, subscribe } from './store';
import { Header } from './components/Header';
import { AdminScreen } from './screens/Admin';
import { ConnectionErrorScreen } from './screens/ConnectionError';
import { JoinScreen } from './screens/Join';
import { ModJoinScreen } from './screens/ModJoin';
import { TeamJoinScreen } from './screens/TeamJoin';
import { ModConsoleScreen } from './screens/ModConsole';
import { LobbyScreen } from './screens/Lobby';
import { RiddleListScreen } from './screens/RiddleList';
import { RiddleDetailScreen } from './screens/RiddleDetail';
import { DrawerScreen } from './screens/Drawer';
import { StandingsScreen } from './screens/Standings';
import { TeamScreen } from './screens/Team';
import { StrikeNoticeScreen } from './screens/StrikeNotice';

// The shell owns phase routing: which top-level screen shows depends on
// the store's phase and, once ready, the event status. This is the
// snapshot contract made visible — every screen renders FROM the
// snapshot, and nothing here talks to the API except through store.js.
//
// /admin is the one exception, and the path decides before the store
// exists: the host console is a separate document (a fresh page load, no
// client-side router), so it must not boot the player store or pull in a
// theme pack. App stays hook-free — the hooks live in the two branches —
// so the switch cannot break the rules of hooks. The match is by path
// segment: `/administrator` is a player path, not the console.
function isAdminPath(pathname) {
  return pathname === '/admin' || pathname.startsWith('/admin/');
}

// The moderator surfaces (S9CW): the link (/m/<code>), the bare code
// form (/mod, where the OIDC callback lands a signed-in moderator), and
// any deeper path. Matched by segment so a player path like /modify is
// not swallowed.
function isModJoinPath(pathname) {
  return (
    pathname === '/m' ||
    pathname.startsWith('/m/') ||
    pathname === '/mod' ||
    pathname.startsWith('/mod/')
  );
}

// A failed reporter boot must not block the app or surface as an
// unhandled rejection, so the whole chain settles into refresh().
function bootReportThenRefresh() {
  initErrorReporting().then(refresh, refresh);
}

// The admin console is a separate document, so it does not boot the
// player store — but it must still report its own errors, and the
// reporter boot is the same idempotent call the player path makes.
function AdminBoot() {
  useEffect(() => {
    initErrorReporting();
  }, []);
  return <AdminScreen />;
}

function App() {
  if (isAdminPath(window.location.pathname)) {
    return <AdminBoot />;
  }
  return <PlayerApp />;
}

function PlayerApp() {
  const [state, setState] = useState(getState());

  useEffect(() => {
    const unsubscribe = subscribe(setState);
    // Boot the reporter before the first request so a failure on boot is
    // reported; without a DSN this loads nothing and refresh starts at
    // once. With a DSN the SDK import is awaited first: a boot failure
    // that fired before Sentry's global handlers were installed would go
    // unreported, which is the whole point of starting here.
    bootReportThenRefresh();
    return unsubscribe;
  }, []);

  if (state.phase === 'booting') {
    return <div class="frame"><main style={{ padding: 16 }}><p class="dim">Waking the Batcomputer…</p></main></div>;
  }

  if (state.phase === 'error') {
    return <ConnectionErrorScreen message={state.error} onRetry={retry} />;
  }

  // A /t/<token> invite link decides the screen in EVERY phase before
  // the role/snapshot routing does: a fresh device must reach the
  // invite landing instead of the join screen, and a logged-in player
  // who opens a link (the switch case) must reach it too — the
  // snapshot routing below would otherwise swallow the path.
  const teamInvite = window.location.pathname.match(/^\/t\/([A-Za-z0-9]+)/);
  if (teamInvite) {
    return <TeamJoinScreen token={teamInvite[1]} copy={state.copy} />;
  }

  if (state.phase === 'join') {
    // The mod link is the only other unauthenticated surface; its path
    // decides which join screen shows before any session exists.
    if (isModJoinPath(window.location.pathname)) {
      return <ModJoinScreen />;
    }
    return <JoinScreen />;
  }

  // phase === 'ready': the role decides the shell. Moderators get the
  // work queue — no tabs, no game chrome (mock: "this is a work
  // queue, not the game").
  const { snapshot, modEvent, copy } = state;
  if (state.role === 'moderator') {
    return (
      <div class="frame">
        <Header eventName={`${modEvent.name} — Moderator`} playerName="console" />
        <ModConsoleScreen modEvent={modEvent} copy={copy} />
      </div>
    );
  }
  if (snapshot.event.status === 'lobby') {
    return (
      <div class="frame">
        <Header eventName={snapshot.event.name} playerName={snapshot.me.display_name} />
        <LobbyScreen copy={copy} />
      </div>
    );
  }
  return <GameShell snapshot={snapshot} copy={copy} />;
}
// In-game shell: header + active tab screen + tab bar. Tabs (and the
// open riddle) are local component state (not the URL) — the PWA is a
// single screen stack at party scale, and preact-router adds nothing
// until deep links exist.
//
// No polling anywhere: the store's SSE stream delivers verdict deltas
// (SCANNING → verdict) and event_status, each routing to refresh().
function GameShell({ snapshot, copy }) {
  const [tab, setTab] = useState('riddles');
  const [openRiddle, setOpenRiddle] = useState(null);

  let screen;
  if (openRiddle) {
    screen = (
      <RiddleDetailScreen
        snapshot={snapshot}
        copy={copy}
        riddleId={openRiddle}
        onBack={() => setOpenRiddle(null)}
        onOpenDrawer={() => { setOpenRiddle(null); setTab('drawer'); }}
      />
    );
  } else if (tab === 'riddles') {
    screen = <RiddleListScreen snapshot={snapshot} copy={copy} onOpenRiddle={setOpenRiddle} />;
  } else if (tab === 'team') {
    screen = <TeamScreen snapshot={snapshot} copy={copy} />;
  } else if (tab === 'standings') {
    screen = <StandingsScreen snapshot={snapshot} copy={copy} />;
  } else {
    screen = <DrawerScreen snapshot={snapshot} copy={copy} />;
  }

  return (
    <div class="frame">
      <Header eventName={snapshot.event.name} playerName={snapshot.me.display_name} />
      {screen}
      {/* The strike-1 interstitial overlays the whole app (mock: dimmed
          board behind). Un-themed by rule — the component carries its
          own plain copy. */}
      {snapshot.me.restriction?.pending_notice && <StrikeNoticeScreen />}
      <nav class="tab-bar">
        <a href="#" class={tab === 'riddles' ? 'active' : ''}
           onClick={(e) => { e.preventDefault(); setOpenRiddle(null); setTab('riddles'); }}>
          <span class="tab-icon">?</span>{copy.tabs.riddles}
        </a>
        <a href="#" class={tab === 'drawer' ? 'active' : ''}
           onClick={(e) => { e.preventDefault(); setOpenRiddle(null); setTab('drawer'); }}>
          <span class="tab-icon">▦</span>{copy.tabs.drawer}
        </a>
        <a href="#" class={tab === 'team' ? 'active' : ''}
           onClick={(e) => { e.preventDefault(); setOpenRiddle(null); setTab('team'); }}>
          <span class="tab-icon">⬡</span>{copy.tabs.team}
        </a>
        <a href="#" class={tab === 'standings' ? 'active' : ''}
           onClick={(e) => { e.preventDefault(); setOpenRiddle(null); setTab('standings'); }}>
          <span class="tab-icon">≡</span>{copy.tabs.standings}
        </a>
      </nav>
    </div>
  );
}

render(<App />, document.getElementById('app'));
