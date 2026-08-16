import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';

import { getState, refresh, subscribe } from './store';
import { Header } from './components/Header';
import { JoinScreen } from './screens/Join';
import { LobbyScreen } from './screens/Lobby';
import { RiddleListScreen } from './screens/RiddleList';
import { RiddleDetailScreen } from './screens/RiddleDetail';
import { DrawerScreen } from './screens/Drawer';

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
    return <JoinScreen />;
  }

  // phase === 'ready': the snapshot drives the rest.
  const { snapshot, copy } = state;
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
// The shell also owns the SCANNING poll: while any riddle tile is
// pending, the moderator verdict could land at any moment, so the
// snapshot refreshes on a 5s interval. SSE deltas (increment 7) will
// replace this; the poll is the honest stopgap.
function GameShell({ snapshot, copy }) {
  const [tab, setTab] = useState('riddles');
  const [openRiddle, setOpenRiddle] = useState(null);

  const hasPending = snapshot.riddles.some((r) => r.state === 'pending');
  useEffect(() => {
    if (!hasPending) return;
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [hasPending]);

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
    screen = <DrawerScreen copy={copy} />;
  }

  return (
    <div class="frame">
      <Header eventName={snapshot.event.name} playerName={snapshot.me.display_name} />
      {screen}
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
