// Lobby screen: joined, but the round hasn't opened yet (ui.md: "the
// lobby screen exists — without it, early joiners hit a dead end").
// Polls the snapshot so the screen flips to the riddle board the moment
// the host opens the round; SSE replaces polling in increment 7.
import { useEffect } from 'preact/hooks';

import { refresh } from '../store';

export function LobbyScreen({ copy }) {
  useEffect(() => {
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main style={{ flex: 1, padding: '32px 16px' }}>
      <div class="verdict-banner sev-cyan">
        <div class="verdict-chip">…</div>
        <div>
          <div class="verdict-headline">{copy.screens.lobby.headline}</div>
          <p class="subtext" style={{ marginTop: 6 }}>{copy.screens.lobby.subtext}</p>
        </div>
      </div>
    </main>
  );
}
