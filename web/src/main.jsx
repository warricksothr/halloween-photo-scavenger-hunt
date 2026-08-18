import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';

import { getState, refresh, subscribe } from './store';
import { Header } from './components/Header';
import { JoinScreen } from './screens/Join';
import { ModJoinScreen } from './screens/ModJoin';
import { ModConsoleScreen } from './screens/ModConsole';
import { LobbyScreen } from './screens/Lobby';
import { RiddleListScreen } from './screens/RiddleList';
import { RiddleDetailScreen } from './screens/RiddleDetail';
import { DrawerScreen } from './screens/Drawer';
import { StrikeNoticeScreen } from './screens/StrikeNotice';

// The shell owns phase routing: which top-level screen shows depends on
// the store's phase and, once ready, the event status. This is the
// snapshot contract made visible — every screen renders FROM the
// snapshot, and nothing here talks to the API except through store.js.
function App() {
  const [state, setState] = useState(getState());

  useEffect(() => {
    const unsubscribe = subscribe(setState);
    refresh(); // boot: the snapshot decides everything
    return unsubscribe;
  }, []);

  if (state.phase === 'booting') {
    return <div class="frame"><main style={{ padding: 16 }}><p class="dim">Waking the Batcomputer…</p></main></div>;
  }

  if (state.phase === 'error') {
    return (
      <div class="frame">
        <main style={{ padding: 16 }}>
          <div class="verdict-banner sev-red">
            <div class="verdict-chip">!</div>
            <div>
              <div class="verdict-headline">Connection Failed</div>
              <p class="subtext" style={{ marginTop: 6 }}>{state.error}</p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (state.phase === 'join') {
    // The mod link is the only other unauthenticated surface; its path
    // decides which join screen shows before any session exists.
    if (window.location.pathname.startsWith('/m/')) {
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
      </nav>
    </div>
  );
}

render(<App />, document.getElementById('app'));
