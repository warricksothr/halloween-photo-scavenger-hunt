import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';

import { initErrorReporting } from './errors';
import { useGameNav } from './nav';
import { isModPath, modLinkCode } from './paths';
import { getState, leaveModerator, refresh, retry, subscribe, switchGame } from './store';
import { defaultCopy } from './theme';
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
    // No event theme exists yet, so the boot line comes from the default
    // pack rather than a string baked into the shell (theme.js).
    const boot = state.copy ?? defaultCopy();
    return <div class="frame" data-testid="app-frame"><main style={{ padding: 16 }}><p class="dim">{boot.screens.boot.loading}</p></main></div>;
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

  // A mod link joins its event whatever else the browser holds: a player
  // session (the host who plays) or a moderator session for another event.
  // A successful join moves the URL to /mod, so this does not loop.
  if (modLinkCode(window.location.pathname)) {
    return <ModJoinScreen />;
  }

  if (state.phase === 'join') {
    // The mod link is the only other unauthenticated surface; its path
    // decides which join screen shows before any session exists.
    if (isModPath(window.location.pathname)) {
      return <ModJoinScreen />;
    }
    return <JoinScreen />;
  }

  // phase === 'ready': the role decides the shell. Moderators get the
  // work queue — no tabs, no game chrome (mock: "this is a work
  // queue, not the game").
  const { snapshot, modEvent, copy } = state;
  if (state.role === 'moderator') {
    // mod-frame lets the console outgrow the phone frame on a tablet or a
    // desktop (ADR 0029); the header names who is moderating.
    return (
      <div class="frame mod-frame" data-testid="app-frame">
        <Header
          eventName={`${modEvent.name} — Moderator`}
          playerName={state.moderator?.label ?? 'console'}
          action={
            // The host who also plays needs a way back to the game; the
            // console has no other link out (ADR 0032).
            <button type="button" class="btn secondary header-action" onClick={leaveModerator}>
              Leave console
            </button>
          }
        />
        <ModConsoleScreen copy={copy} moderatorId={state.moderator?.id ?? null} />
      </div>
    );
  }
  if (snapshot.event.status === 'lobby') {
    return (
      <div class="frame" data-testid="app-frame">
        <div class="top-bar">
          <Header
            eventName={snapshot.event.name}
            playerName={snapshot.me.display_name}
            action={<SwitchGame copy={copy} />}
          />
        </div>
        <LobbyScreen copy={copy} />
      </div>
    );
  }
  // Keyed by event: a different game mounts a fresh shell, so no screen,
  // drawer return target or selection carries over from the last one
  // (ADR 0036).
  return <GameShell key={snapshot.event.id} snapshot={snapshot} copy={copy} />;
}
// Back to the landing page's Open Cases with this game still listed there
// (ADR 0033): how a player picks another event without waiting out the
// session. Signing out for good lives on the Team tab.
function SwitchGame({ copy }) {
  return (
    <button type="button" class="btn secondary header-action" onClick={switchGame}>
      {copy.screens.header.switchGame}
    </button>
  );
}

// In-game shell: header + tabs pinned at the top, then the screen. The
// screen (tab, open riddle, the riddle the drawer returns to) lives in
// history entries rather than the URL, so Back and the iOS edge swipe move
// between screens (nav.js, ADR 0036).
//
// No polling anywhere: the store's SSE stream delivers verdict deltas
// (SCANNING → verdict) and event_status, each routing to refresh().
function GameShell({ snapshot, copy }) {
  const { nav, go, back, leave, returnWith, selected } = useGameNav(snapshot.event.id);
  const { tab } = nav;

  let screen;
  if (tab === 'riddles' && nav.riddle) {
    screen = (
      <RiddleDetailScreen
        // A fresh screen per riddle, so a photo selected on the way back
        // from the drawer seeds its selection.
        key={nav.riddle}
        snapshot={snapshot}
        copy={copy}
        riddleId={nav.riddle}
        initialSelected={selected}
        onBack={back}
        onGone={leave}
        onOpenDrawer={() => go({ tab: 'drawer', returnTo: nav.riddle })}
      />
    );
  } else if (tab === 'riddles') {
    screen = (
      <RiddleListScreen
        snapshot={snapshot}
        copy={copy}
        onOpenRiddle={(riddle) => go({ tab: 'riddles', riddle })}
      />
    );
  } else if (tab === 'team') {
    screen = <TeamScreen snapshot={snapshot} copy={copy} />;
  } else if (tab === 'standings') {
    screen = <StandingsScreen snapshot={snapshot} copy={copy} />;
  } else {
    screen = (
      <DrawerScreen
        snapshot={snapshot}
        copy={copy}
        returnTo={nav.returnTo}
        onReturn={back}
        onUploadedFor={returnWith}
      />
    );
  }

  return (
    <div class="frame" data-testid="app-frame">
      {/* Header and tabs pinned together at the top (ADR 0034): every
          control stays on screen while the board scrolls, and nothing
          depends on where Safari's bottom bar sits. */}
      <div class="top-bar">
        <Header
          eventName={snapshot.event.name}
          playerName={snapshot.me.display_name}
          action={<SwitchGame copy={copy} />}
        />
        <GameTabs tab={tab} copy={copy} onTab={(next) => go({ tab: next })} />
      </div>
      {screen}
      {/* The strike-1 interstitial overlays the whole app (mock: dimmed
          board behind). Un-themed by rule — the component carries its
          own plain copy. */}
      {snapshot.me.restriction?.pending_notice && <StrikeNoticeScreen />}
    </div>
  );
}

const TABS = [
  ['riddles', '?'],
  ['drawer', '▦'],
  ['team', '⬡'],
  ['standings', '≡'],
];

function GameTabs({ tab, copy, onTab }) {
  return (
    <nav class="tab-bar">
      {TABS.map(([key, icon]) => (
        <a key={key} href="#" class={tab === key ? 'active' : ''}
           aria-current={tab === key ? 'page' : undefined}
           onClick={(e) => { e.preventDefault(); onTab(key); }}>
          <span class="tab-icon">{icon}</span>{copy.tabs[key]}
        </a>
      ))}
    </nav>
  );
}

render(<App />, document.getElementById('app'));
