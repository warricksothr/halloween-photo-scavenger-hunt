// Riddles view for the host console (S9CZ) — the panel S9CX stubbed.
//
// The admin API already owned riddle CRUD (server/app/events.py), including
// the two refusals worth surfacing: a 404 for a riddle that is gone and a
// 409 for deleting one that submissions reference. This is the screen that
// drives it, following the shape in docs/impl/mocks/admin-riddles.html:
// numbered rows with Edit/reorder/Delete, and an add box that appends.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';

export function AdminRiddles({ onSessionExpired }) {
  const [events, setEvents] = useState([]);
  const [eventsLoaded, setEventsLoaded] = useState(false);
  const [eventId, setEventId] = useState(null);
  const [riddles, setRiddles] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // riddle id being edited
  const [editText, setEditText] = useState('');
  const [confirming, setConfirming] = useState(null); // riddle id awaiting delete

  // A 401 mid-use means the admin session expired; the shell owns the
  // recovery, and the panel clears so the board does not outlive the login.
  function expired() {
    setEvents([]);
    setRiddles([]);
    setEditing(null);
    setConfirming(null);
    setError(null);
    onSessionExpired?.();
  }

  useEffect(() => {
    let live = true;
    (async () => {
      const result = await api.adminEvents();
      if (!live) return;
      if (result?.unauthenticated) {
        expired();
        return;
      }
      setEventsLoaded(true);
      if (result?.error) {
        setError(result.message);
        return;
      }
      setEvents(result);
      setEventId((current) => current ?? result[0]?.id ?? null);
    })();
    return () => {
      live = false;
    };
    // `expired` reads only setters and the prop; it never changes identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!eventId) return;
    let live = true;
    (async () => {
      const result = await api.adminRiddles(eventId);
      if (!live) return;
      if (result?.unauthenticated) {
        expired();
        return;
      }
      if (result?.error) setError(result.message);
      else {
        // A successful load clears the previous event's failure, or the old
        // message would sit above the new event's valid rows.
        setError(null);
        setRiddles(result);
      }
    })();
    return () => {
      live = false;
    };
    // The shell unmounts this panel on a 401, so the prop's identity is
    // irrelevant to the fetch; re-running on it would refetch the same list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  // Takes the event explicitly so a response can never be applied to a
  // different selection than the one it was fetched for.
  async function fetchRiddles(targetId) {
    const result = await api.adminRiddles(targetId);
    if (result?.unauthenticated) {
      expired();
      return result;
    }
    if (result?.error) return result;
    setError(null);
    setRiddles(result);
    return result;
  }

  // One guard for every riddle mutation, held across the refetch: a reorder
  // is several PATCHes and the list must not offer a second move until the
  // new order is on screen (same rule as the event lifecycle in S9CY).
  //
  // The refetch happens even when the action errors. A multi-write action
  // can fail halfway — the first PATCH of a move may have landed — so the
  // server is not the list on screen, and leaving it would let the next
  // move compute from stale orders.
  async function mutate(action) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      const refreshed = await fetchRiddles(eventId);
      if (result?.error) setError(result.message);
      else if (refreshed?.error) setError(refreshed.message);
      return result;
    } finally {
      setBusy(false);
    }
  }

  async function onAdd(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const text = form.elements.text.value.trim();
    if (!text) return;
    // The mock says add appends; max+1 also survives a list a partial
    // reorder left with duplicate or sparse orders.
    const next = riddles.reduce((top, r) => Math.max(top, r.sort_order), -1) + 1;
    const result = await mutate(() =>
      api.adminCreateRiddle(eventId, { text, sort_order: next }),
    );
    if (result && !result.error) form.reset();
  }

  async function onMove(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= riddles.length) return;
    const reordered = [...riddles];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    await mutate(async () => {
      // Renumber every row whose order does not match its new position —
      // normally the two that moved, plus any duplicate orders already in
      // the table (sort_order has no unique constraint).
      for (let position = 0; position < reordered.length; position += 1) {
        const riddle = reordered[position];
        if (riddle.sort_order === position) continue;
        const result = await api.adminPatchRiddle(eventId, riddle.id, {
          sort_order: position,
        });
        if (result?.error) return result;
      }
      return { ok: true };
    });
  }

  async function onSaveEdit(riddleId) {
    const text = editText.trim();
    if (!text) return;
    const result = await mutate(() =>
      api.adminPatchRiddle(eventId, riddleId, { text }),
    );
    if (result && !result.error) setEditing(null);
  }

  async function onDelete(riddleId) {
    const result = await mutate(() => api.adminDeleteRiddle(eventId, riddleId));
    if (result && !result.error) setConfirming(null);
  }

  if (!eventsLoaded) {
    return (
      <div class="admin-panel">
        <h2>Riddles</h2>
        <p class="admin-note">Loading events…</p>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div class="admin-panel">
        <h2>Riddles</h2>
        {error ? (
          <div class="admin-error">{error}</div>
        ) : (
          <p class="admin-note">
            Create an event on the Events tab first; riddles belong to an
            event.
          </p>
        )}
      </div>
    );
  }

  return (
    <>
      {error && <div class="admin-error">{error}</div>}

      <div class="admin-panel">
        <div class="admin-panel-head">
          <h2>Riddles</h2>
          <div class="admin-field admin-field-inline">
            <label for="riddle-event">Event</label>
            <select
              class="admin-input"
              id="riddle-event"
              value={eventId ?? ''}
              // Disabled while a mutation is in flight: a switch mid-write
              // would let the write's refetch land under the new event.
              disabled={busy}
              onChange={(e) => {
                setRiddles([]);
                setEditing(null);
                setConfirming(null);
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
        <p class="admin-note">
          12–15 per event is the sweet spot. Players see the full board the
          moment the round opens, so order is presentation, not progression.
        </p>

        {riddles.length === 0 ? (
          <p class="admin-note">
            No riddles yet. The round cannot open until at least one exists.
          </p>
        ) : (
          riddles.map((riddle, index) => (
            <div key={riddle.id} class="admin-riddle">
              <span class="admin-order">{String(index + 1).padStart(2, '0')}</span>
              {editing === riddle.id ? (
                <span class="admin-riddle-body">
                  <textarea
                    class="admin-input"
                    aria-label={`Riddle ${index + 1} text`}
                    value={editText}
                    onInput={(e) => setEditText(e.target.value)}
                  />
                  <span class="admin-actions">
                    <button
                      class="admin-btn secondary"
                      disabled={busy || !editText.trim()}
                      onClick={() => onSaveEdit(riddle.id)}
                    >
                      Save
                    </button>
                    <button
                      class="admin-btn secondary"
                      type="button"
                      onClick={() => setEditing(null)}
                    >
                      Cancel
                    </button>
                  </span>
                </span>
              ) : (
                <span class="admin-riddle-body">{riddle.text}</span>
              )}
              <span class="admin-actions">
                {editing === riddle.id ? null : confirming === riddle.id ? (
                  <>
                    <button
                      class="admin-btn danger"
                      disabled={busy}
                      onClick={() => onDelete(riddle.id)}
                    >
                      {busy ? 'Deleting…' : 'Confirm delete'}
                    </button>
                    <button
                      class="admin-btn secondary"
                      type="button"
                      onClick={() => setConfirming(null)}
                    >
                      Keep
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      class="admin-btn secondary"
                      disabled={busy}
                      onClick={() => {
                        setEditing(riddle.id);
                        setEditText(riddle.text);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      class="admin-btn secondary"
                      aria-label={`Move riddle ${index + 1} up`}
                      disabled={busy || index === 0}
                      onClick={() => onMove(index, -1)}
                    >
                      ↑
                    </button>
                    <button
                      class="admin-btn secondary"
                      aria-label={`Move riddle ${index + 1} down`}
                      disabled={busy || index === riddles.length - 1}
                      onClick={() => onMove(index, 1)}
                    >
                      ↓
                    </button>
                    <button
                      class="admin-btn secondary"
                      disabled={busy}
                      onClick={() => setConfirming(riddle.id)}
                    >
                      Delete
                    </button>
                  </>
                )}
              </span>
            </div>
          ))
        )}

        <form class="admin-add-riddle" onSubmit={onAdd}>
          <div class="admin-field">
            <label for="riddle-text">Add a riddle</label>
            <textarea
              class="admin-input"
              id="riddle-text"
              name="text"
              rows="2"
              placeholder="The subject must be findable and photographable at the venue — check it in person before the night."
            />
          </div>
          <div class="admin-actions">
            <button class="admin-btn" type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Add to board'}
            </button>
            <span class="admin-dim">Appends to the end; reorder with ↑↓.</span>
          </div>
        </form>
      </div>
    </>
  );
}
