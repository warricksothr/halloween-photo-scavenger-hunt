// Header chrome: event name + player codename (mock: app-header).
// Present on every in-game screen; the join screen renders without it
// because there is no player yet. ``action`` puts one control beside the
// name: Leave console for a moderator (ADR 0032), Switch Case for a
// player (ADR 0033).
import './header.css';

export function Header({ eventName, playerName, action = null }) {
  const name = <span class="player-name">{playerName}</span>;
  return (
    <header class="app-header">
      <span class="event-name">{eventName}</span>
      {action ? (
        <span class="app-header-end">
          {name}
          {action}
        </span>
      ) : (
        name
      )}
    </header>
  );
}
