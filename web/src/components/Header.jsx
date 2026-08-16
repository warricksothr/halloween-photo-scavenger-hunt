// Header chrome: event name + player codename (mock: app-header).
// Present on every in-game screen; the join screen renders without it
// because there is no player yet.
export function Header({ eventName, playerName }) {
  return (
    <header class="app-header">
      <span class="event-name">{eventName}</span>
      <span class="player-name">{playerName}</span>
    </header>
  );
}
