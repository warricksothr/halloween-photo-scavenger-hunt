// Lobby screen: joined, but the round hasn't opened yet (ui.md: "the
// lobby screen exists — without it, early joiners hit a dead end").
// No polling here: the store's SSE stream delivers event_status and
// refreshes the snapshot the moment the host opens the round.

export function LobbyScreen({ copy }) {
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
