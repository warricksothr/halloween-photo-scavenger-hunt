import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';

import { getState, refresh, subscribe } from './store';
import { Header } from './components/Header';
import { JoinScreen } from './screens/Join';
import { LobbyScreen } from './screens/Lobby';
import { RiddleListScreen } from './screens/RiddleList';

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
  return (
    <div class="frame">
      <Header eventName={snapshot.event.name} playerName={snapshot.me.display_name} />
      {snapshot.event.status === 'lobby'
        ? <LobbyScreen copy={copy} />
        : <RiddleListScreen snapshot={snapshot} copy={copy} />}
    </div>
  );
}

render(<App />, document.getElementById('app'));
