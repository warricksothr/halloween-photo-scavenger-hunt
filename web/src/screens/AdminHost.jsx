// Host actions view for the host console (S9D0) — the panel S9CX stubbed.
//
// The host-only reversal endpoint already shipped (server/app/events.py);
// this is the screen that drives it: pick an event, pick a player, read
// their strike history, and reverse a strike behind a confirm step. The
// refetch after a reversal is the point — the row must show the reversal
// and the restriction must drop, or the host cannot tell it landed.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';

const LEVELS = { 1: 'Warning', 2: 'Cooldown', 3: 'Ban' };
const RESTRICTIONS = { 0: 'Clean', 1: 'Warned', 2: 'Cooldown', 3: 'Banned' };

function when(epochSeconds) {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString();
}

export function AdminHost() {
  const [events, setEvents] = useState([]);
  const [eventsLoaded, setEventsLoaded] = useState(false);
  const [eventId, setEventId] = useState(null);
  const [players, setPlayers] = useState([]);
  const [playerId, setPlayerId] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(null); // strike id awaiting confirm
  const [reason, setReason] = useState('');

  useEffect(() => {
    let live = true;
    (async () => {
      const result = await api.adminEvents();
      if (!live) return;
      setEventsLoaded(true);
      if (result?.error) {
        setError(result.message);
        return;
      }
      if (result?.unauthenticated) return;
      setEvents(result);
      setEventId((current) => current ?? result[0]?.id ?? null);
    })();
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (!eventId) return;
    let live = true;
    (async () => {
      const result = await api.adminPlayers(eventId);
      if (!live || result?.unauthenticated) return;
      if (result?.error) {
        setError(result.message);
        return;
      }
      setError(null);
      setPlayers(result);
      // Default to the player with a strike to act on; a clean party
      // still lists its players so the history is reachable.
      setPlayerId((current) => {
        if (result.some((p) => p.id === current)) return current;
        const flagged = result.find((p) => p.strikes.some((s) => !s.reversed_at));
        return flagged?.id ?? result[0]?.id ?? null;
      });
    })();
    return () => {
      live = false;
    };
  }, [eventId]);

  // Takes the event explicitly so a response can never be applied to a
  // different selection than the one it was fetched for.
  async function fetchPlayers(targetId) {
    const result = await api.adminPlayers(targetId);
    if (result?.unauthenticated || result?.error) return result;
    setError(null);
    setPlayers(result);
    return result;
  }

  // One guard for the reversal, held across the refetch: the row must not
  // offer a second reversal until the first result is on screen. The
  // refetch happens even when the action errors, so a 409 the host missed
  // still leaves the history honest.
  async function mutate(action) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      const refreshed = await fetchPlayers(eventId);
      if (result?.error) setError(result.message);
      else if (refreshed?.error) setError(refreshed.message);
      return result;
    } finally {
      setBusy(false);
    }
  }

  async function onReverse(strikeId) {
    const result = await mutate(() => api.adminReverseStrike(strikeId, reason.trim()));
    if (result && !result.error) {
      setConfirming(null);
      setReason('');
    }
  }

  function selectPlayer(id) {
    setPlayerId(id);
    setConfirming(null);
    setReason('');
  }

  if (!eventsLoaded) {
    return (
      <div class="admin-panel">
        <h2>Host actions</h2>
        <p class="admin-note">Loading events…</p>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div class="admin-panel">
        <h2>Host actions</h2>
        {error ? (
          <div class="admin-error">{error}</div>
        ) : (
          <p class="admin-note">
            Create an event on the Events tab first; strikes belong to a
            player in an event.
          </p>
        )}
      </div>
    );
  }

  const selected = players.find((player) => player.id === playerId) ?? null;

  return (
    <>
      {error && <div class="admin-error">{error}</div>}

      <div class="admin-panel">
        <div class="admin-panel-head">
          <h2>Host actions</h2>
          <div class="admin-field admin-field-inline">
            <label for="host-event">Event</label>
            <select
              class="admin-input"
              id="host-event"
              value={eventId ?? ''}
              disabled={busy}
              onChange={(e) => {
                setPlayers([]);
                selectPlayer(null);
                setError(null);
                setEventId(e.target.value);
              }}
            >
              {events.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} ({item.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        {players.length === 0 ? (
          <p class="admin-note">
            No players yet. Strikes appear here once a moderator flags a
            submission.
          </p>
        ) : (
          <>
            <div class="admin-field admin-field-inline">
              <label for="host-player">Player</label>
              <select
                class="admin-input"
                id="host-player"
                value={playerId ?? ''}
                disabled={busy}
                onChange={(e) => selectPlayer(e.target.value)}
              >
                {players.map((player) => {
                  const count = player.strikes.filter(
                    (s) => !s.reversed_at,
                  ).length;
                  return (
                    <option key={player.id} value={player.id}>
                      {player.display_name}
                      {count ? ` — ${count} strike${count === 1 ? '' : 's'}` : ''}
                    </option>
                  );
                })}
              </select>
            </div>

            {selected && (
              <>
                <p class="admin-note">
                  Restriction:{' '}
                  {RESTRICTIONS[selected.restriction.level] ??
                    `Level ${selected.restriction.level}`}
                  {selected.restriction.cooldown_until
                    ? ` until ${when(selected.restriction.cooldown_until)}`
                    : ''}
                  . A reversal drops the ladder one rung; it does not
                  restore the flagged photo.
                </p>

                {selected.strikes.length === 0 ? (
                  <p class="admin-note">
                    No strikes on record for {selected.display_name}.
                  </p>
                ) : (
                  selected.strikes.map((strike) => (
                    <div
                      key={strike.id}
                      class={`admin-strike${strike.reversed_at ? ' reversed' : ''}`}
                    >
                      <span class="admin-order">{strike.level}</span>
                      <span class="admin-strike-body">
                        <strong>{LEVELS[strike.level] ?? 'Strike'}</strong>
                        {strike.note ? ` — ${strike.note}` : ''}
                        <span class="admin-dim">
                          {' · '}
                          {when(strike.created_at)}
                          {strike.cooldown_until
                            ? ` · cooldown to ${when(strike.cooldown_until)}`
                            : ''}
                        </span>
                      </span>
                      <span class="admin-actions admin-strike-actions">
                        {strike.reversed_at ? (
                          <span class="admin-dim">
                            Reversed {when(strike.reversed_at)}
                          </span>
                        ) : confirming === strike.id ? (
                          <>
                            <input
                              class="admin-input admin-reason"
                              type="text"
                              aria-label={`Reversal reason for strike ${strike.level}`}
                              placeholder="Reason (optional)"
                              value={reason}
                              onInput={(e) => setReason(e.target.value)}
                            />
                            <button
                              class="admin-btn danger"
                              disabled={busy}
                              onClick={() => onReverse(strike.id)}
                            >
                              {busy ? 'Reversing…' : 'Confirm reversal'}
                            </button>
                            <button
                              class="admin-btn secondary"
                              type="button"
                              onClick={() => {
                                setConfirming(null);
                                setReason('');
                              }}
                            >
                              Keep
                            </button>
                          </>
                        ) : (
                          <button
                            class="admin-btn secondary"
                            disabled={busy}
                            onClick={() => {
                              setConfirming(strike.id);
                              setReason('');
                            }}
                          >
                            Reverse
                          </button>
                        )}
                      </span>
                    </div>
                  ))
                )}
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}
