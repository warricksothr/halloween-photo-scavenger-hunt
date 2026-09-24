// Events view for the host console (S9CY) — the panel S9CX stubbed.
//
// The admin API already owned the whole lifecycle (server/app/events.py);
// this is the UI that drives it: list, create, open, close, purge. The
// codes panel after creation hands out the links at once; each event's
// "Links & QR" shows them again later, with a print sheet and downloads
// for the door (ADR 0026).
import { createPortal } from 'preact/compat';
import { useRef, useState } from 'preact/hooks';

import { api } from '../api';
import { Qr, qrPngBlob, qrSvgString, saveBlob } from '../components/Qr';

const VISIBILITY = [
  { value: 'live', label: 'Live during the round' },
  { value: 'final-reveal', label: 'Sealed until the final reveal' },
];

// Only one theme pack exists; the choice is a select because new packs are
// config + CSS, never a fork (design.md), so the control is real, not fake.
const THEMES = [{ value: 'arkham', label: 'Batman: Arkham' }];

function when(epochSeconds) {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString();
}

export function AdminEvents({ initialEvents, onSessionExpired }) {
  const [events, setEvents] = useState(initialEvents);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [created, setCreated] = useState(null); // event plus its codes
  const [purgeFor, setPurgeFor] = useState(null); // event awaiting confirm
  const [confirmName, setConfirmName] = useState('');
  // One event's links open at a time: its codes, fetched on demand.
  const [linksFor, setLinksFor] = useState(null); // { id, codes }
  // The latest links request. Each click bumps it, so a slow response for
  // an event the host has since moved off (or closed) is dropped instead
  // of reopening the wrong event's links.
  const linksRequestRef = useRef(0);

  // Close the links and drop any response still in flight: used when the
  // event goes away or the session does, so no codes outlive either.
  function closeLinks() {
    linksRequestRef.current += 1;
    setLinksFor(null);
  }

  async function reload() {
    const result = await api.adminEvents();
    if (result?.unauthenticated) {
      // The lifecycle is a mutation surface; once the session is gone the
      // buttons must go with it, so the shell takes back the view.
      setEvents([]);
      setCreated(null);
      setPurgeFor(null);
      closeLinks();
      setError(null);
      onSessionExpired?.();
    } else if (result?.error) setError(result.message);
    else setEvents(result);
  }

  // Every mutation funnels through one guard: `busy` cannot strand a
  // button, the API's message is what the host reads, and a lifecycle
  // change holds the guard across the refetch. Releasing it at the request
  // would leave the row showing its old status with its old action enabled,
  // so a second click could fire the transition the server just refused.
  async function mutate(action, { refetch = false } = {}) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      if (result?.error) {
        setError(result.message);
        return result;
      }
      if (refetch) await reload();
      return result;
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const result = await mutate(
      () =>
        api.adminCreateEvent({
          name: data.get('name').trim(),
          theme: data.get('theme'),
          leaderboard_visibility: data.get('visibility'),
          team_size_limit: Number(data.get('team_size')),
        }),
      { refetch: true },
    );
    if (result && !result.error) {
      setCreated(result);
      setShowCreate(false);
      form.reset();
    }
  }

  async function toggleLinks(item) {
    const request = ++linksRequestRef.current;
    if (linksFor?.id === item.id) {
      setLinksFor(null);
      return;
    }
    setError(null);
    const result = await api.adminEventCodes(item.id);
    if (request !== linksRequestRef.current) return;
    if (result?.unauthenticated) {
      // Same contract as reload: a dead session hands the view back.
      await reload();
    } else if (result?.error) setError(result.message);
    else setLinksFor({ id: item.id, codes: result });
  }

  async function onPurge(event) {
    event.preventDefault();
    const target = purgeFor;
    const result = await mutate(
      () => api.adminPurgeEvent(target.id, confirmName),
      { refetch: true },
    );
    if (result && !result.error) {
      setPurgeFor(null);
      setConfirmName('');
      if (created?.id === target.id) setCreated(null);
      closeLinks();
    }
  }

  return (
    <>
      {error && <div class="admin-error">{error}</div>}

      {created && <CodesPanel event={created} onDismiss={() => setCreated(null)} />}

      <div class="admin-panel">
        <div class="admin-panel-head">
          <h2>Events</h2>
          <button
            class="admin-btn secondary"
            onClick={() => setShowCreate((open) => !open)}
          >
            {showCreate ? 'Cancel' : 'New event'}
          </button>
        </div>

        {showCreate && (
          <form class="admin-create" onSubmit={onCreate}>
            <div class="admin-field">
              <label for="event-name">Event name</label>
              <input
                class="admin-input"
                id="event-name"
                name="name"
                type="text"
                maxLength={120}
                required
                placeholder="Gotham Halloween 2026"
              />
            </div>
            <div class="admin-field">
              <label for="event-theme">Theme pack</label>
              <select class="admin-input" id="event-theme" name="theme">
                {THEMES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div class="admin-field">
              <label for="event-visibility">Leaderboard</label>
              <select class="admin-input" id="event-visibility" name="visibility">
                {VISIBILITY.map((v) => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>
            <div class="admin-field">
              <label for="event-team-size">Team size limit</label>
              <input
                class="admin-input"
                id="event-team-size"
                name="team_size"
                type="number"
                min="1"
                max="32"
                value="1"
              />
              <p class="admin-note">
                1 = every player flies solo. Higher values unlock team
                invites and a shared evidence drawer per team.
              </p>
            </div>
            <button class="admin-btn" type="submit" disabled={busy}>
              {busy ? 'Creating…' : 'Create event'}
            </button>
          </form>
        )}

        {events.length === 0 ? (
          <p class="admin-note">No events yet. Create one to get the join and
          moderator codes.</p>
        ) : (
          events.map((item) => (
            <div key={item.id} class="admin-event">
              <div class="admin-row">
                <span class="admin-event-name">{item.name}</span>
                <span class="admin-status">{item.status}</span>
                <span class="admin-dim admin-event-when">{when(item.created_at)}</span>
                <span class="admin-actions">
                  <button class="admin-btn secondary"
                          aria-expanded={linksFor?.id === item.id}
                          onClick={() => toggleLinks(item)}>
                    {linksFor?.id === item.id ? 'Hide links' : 'Links & QR'}
                  </button>
                  {item.status === 'lobby' && (
                    <button class="admin-btn secondary" disabled={busy}
                            onClick={() =>
                              mutate(() => api.adminOpenEvent(item.id), {
                                refetch: true,
                              })}>
                      Open
                    </button>
                  )}
                  {item.status === 'open' && (
                    <button class="admin-btn secondary" disabled={busy}
                            onClick={() =>
                              mutate(() => api.adminCloseEvent(item.id), {
                                refetch: true,
                              })}>
                      Close
                    </button>
                  )}
                  {item.status === 'closed' && (
                    <button class="admin-btn secondary" disabled={busy}
                            onClick={() => { setPurgeFor(item); setConfirmName(''); }}>
                      Purge
                    </button>
                  )}
                </span>
              </div>

              {linksFor?.id === item.id && (
                <EventLinks event={item} codes={linksFor.codes} />
              )}

              {purgeFor?.id === item.id && (
                <form class="admin-purge" onSubmit={onPurge}>
                  <p>
                    Purging <b>{item.name}</b> deletes the event, its
                    submissions, and its photos. This cannot be undone.
                  </p>
                  <div class="admin-field">
                    <label for={`confirm-${item.id}`}>
                      Type the event name to confirm
                    </label>
                    <input
                      class="admin-input"
                      id={`confirm-${item.id}`}
                      type="text"
                      value={confirmName}
                      onInput={(e) => setConfirmName(e.target.value)}
                    />
                  </div>
                  <div class="admin-actions">
                    <button
                      class="admin-btn danger"
                      type="submit"
                      disabled={busy || confirmName !== item.name}
                    >
                      {busy ? 'Purging…' : 'Purge event'}
                    </button>
                    <button
                      class="admin-btn secondary"
                      type="button"
                      onClick={() => { setPurgeFor(null); setConfirmName(''); }}
                    >
                      Keep it
                    </button>
                  </div>
                </form>
              )}
            </div>
          ))
        )}
      </div>
    </>
  );
}

function CodesPanel({ event, onDismiss }) {
  return (
    <div class="admin-panel admin-codes">
      <div class="admin-panel-head">
        <h2>{event.name} is in the lobby</h2>
        <button class="admin-btn secondary" onClick={onDismiss}>Done</button>
      </div>
      <p class="admin-note">
        Hand these out now, or later from the event's Links &amp; QR. A
        purged event's codes are gone for good.
      </p>
      <div class="admin-grid">
        <CodeCard
          title="Player join link"
          url={joinUrl(event.join_code)}
          note="Print or screen-share at the door. Scanning it is the only login players ever do."
        />
        <CodeCard
          title="Moderator link"
          url={modUrl(event.mod_code)}
          note="Send privately to whoever runs the review queue. Never project this one."
        />
      </div>
      <p class="admin-note">
        The round opens from the list below once at least one riddle exists.
      </p>
    </div>
  );
}

function joinUrl(code) {
  return `${window.location.origin}/j/${code}`;
}

function modUrl(code) {
  return `${window.location.origin}/m/${code}`;
}

// A filename-safe stem from the event name, for the downloads.
function slug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'event';
}

function EventLinks({ event, codes }) {
  const [showMod, setShowMod] = useState(false);
  const url = joinUrl(codes.join_code);
  const stem = `${slug(event.name)}-join-qr`;
  return (
    <div class="admin-links">
      <div class="admin-grid">
        <CodeCard
          title="Player join link"
          url={url}
          note="Print or screen-share at the door. Scanning it is the only login players ever do."
          actions={
            <>
              <button class="admin-btn secondary" onClick={() => window.print()}>
                Print
              </button>
              <button class="admin-btn secondary"
                      onClick={() =>
                        saveBlob(
                          new Blob([qrSvgString(url)], { type: 'image/svg+xml' }),
                          `${stem}.svg`,
                        )}>
                SVG
              </button>
              <button class="admin-btn secondary"
                      onClick={async () => {
                        const blob = await qrPngBlob(url);
                        if (blob) saveBlob(blob, `${stem}.png`);
                      }}>
                PNG
              </button>
            </>
          }
        />
        {showMod ? (
          <CodeCard
            title="Moderator link"
            url={modUrl(codes.mod_code)}
            note="Send privately to whoever runs the review queue. Never project this one."
          />
        ) : (
          <div class="admin-code">
            <div class="admin-status">Moderator link</div>
            <p class="admin-note">
              Hidden so it never ends up on a projected screen.
            </p>
            <button class="admin-btn secondary" onClick={() => setShowMod(true)}>
              Reveal moderator link
            </button>
          </div>
        )}
      </div>
      {/* The print sheet lives on <body>, so the print stylesheet can hide
          everything else outright rather than leave blank pages behind. */}
      {createPortal(
        <div class="admin-print-sheet" aria-hidden="true">
          <h1>{event.name}</h1>
          <Qr text={url} label="Join QR code" size={512} class="admin-print-qr" />
          <p class="admin-print-call">Scan to join</p>
          <p class="admin-print-url">{url}</p>
        </div>,
        document.body,
      )}
    </div>
  );
}

function CodeCard({ title, url, note, actions }) {
  const [copied, setCopied] = useState(false);
  const canCopy = Boolean(navigator.clipboard?.writeText);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      // Plain HTTP has no clipboard; the URL stays selectable text.
      setCopied(false);
    }
  }

  return (
    <div class="admin-code">
      <div class="admin-status">{title}</div>
      <Qr text={url} label={`${title} QR code`} />
      <code class="admin-code-url">{url}</code>
      {canCopy && (
        <button class="admin-btn secondary" onClick={onCopy}>
          {copied ? 'Copied' : 'Copy link'}
        </button>
      )}
      {actions && <div class="admin-code-actions">{actions}</div>}
      <p class="admin-note">{note}</p>
    </div>
  );
}
