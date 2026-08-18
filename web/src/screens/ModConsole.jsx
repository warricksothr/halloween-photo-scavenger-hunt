// Moderator console — the queue (increment 7).
//
// Layout follows docs/impl/mocks/moderator.html: a work queue, not the
// game — queue list on top (oldest first, claim state, flag badge),
// the open item below with photo + riddle/player panel, one-tap
// verdicts, and an optional flavor-text picker.
//
// Concurrency is the server's (ADR 0002): a lost verdict race comes
// back 409 and the queue refetches; the claim is advisory and shown to
// other moderators, never a lock. Queue freshness comes from the
// store's SSE stream: submission_new and queue_resolved deltas trigger
// a refetch — no polling.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';
import { subscribeDeltas } from '../store';

// One-tap verdict buttons, in the mock's order and severity. The
// canned flavor lines come from the theme pack's verdict bank so the
// moderator can attach in-fiction copy without typing.
const VERDICTS = [
  { key: 'verified', label: '✓ Riddle Solved', style: { background: 'var(--green)' } },
  { key: 'obscured', label: 'Obscured', secondary: true },
  { key: 'too_small', label: 'Too Small', secondary: true },
  { key: 'misaligned', label: 'Misaligned', secondary: true },
  { key: 'not_found', label: 'Subject Not Found', danger: true },
];

function ago(createdAt) {
  const mins = Math.max(0, Math.round((Date.now() / 1000 - createdAt) / 60));
  return mins < 1 ? 'just now' : `${mins} min ago`;
}

export function ModConsoleScreen({ modEvent, copy }) {
  const [queue, setQueue] = useState(null); // null = loading
  const [openId, setOpenId] = useState(null);
  const [flavor, setFlavor] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  // Conduct UI: the danger button arms a confirm step before firing
  // (mock: "confirm step optional" — we take it; one-tap + danger is a
  // mis-tap waiting to happen), and the open item's player history
  // (strikes included) loads lazily for consistency of judgment.
  const [confirming, setConfirming] = useState(false);
  const [history, setHistory] = useState(null);

  async function reload() {
    const result = await api.modQueue();
    if (result.error) {
      setError(result.message);
      return;
    }
    setQueue(result);
    // If the open item got resolved by another mod (or the round
    // closed), close the detail — the queue is the source of truth.
    setOpenId((current) =>
      current && result.some((item) => item.id === current) ? current : null);
  }

  useEffect(() => {
    reload();
    // submission_new: the queue grew; queue_resolved: an item left it
    // (possibly via another moderator). Either way, refetch.
    const unsubscribe = subscribeDeltas((name) => {
      if (name === 'submission_new' || name === 'queue_resolved') reload();
    });
    return unsubscribe;
  }, []);

  function open(item) {
    setOpenId(item.id);
    setError(null);
    setConfirming(false);
    setHistory(null);
    api.modPlayerHistory(item.player.id).then((result) => {
      if (!result.error) setHistory(result);
    });
    // Opening soft-claims (ADR 0002): advisory, tells other moderators
    // someone is looking. Fire-and-forget; a lost claim means nothing.
    api.modClaim(item.id).then(() => reload());
  }

  async function sendVerdict(item, verdictKey) {
    if (busy) return;
    setBusy(true);
    setError(null);
    const result = await api.modVerdict(item.id, verdictKey, flavor.trim());
    if (result?.error) {
      // already_resolved is the race loss — the refetch shows the item
      // gone, which is feedback enough; everything else gets a banner.
      if (result.error !== 'already_resolved') setError(result.message);
    } else {
      setFlavor('');
      setOpenId(null);
    }
    await reload();
    setBusy(false);
  }

  async function sendInappropriate(item) {
    if (busy) return;
    setBusy(true);
    setError(null);
    // Conduct copy is plain and hardcoded here by rule (design.md):
    // nothing themed ever touches a conduct surface.
    const result = await api.modInappropriate(item.id, '', null);
    if (result?.error) {
      if (result.error !== 'already_resolved') setError(result.message);
    } else {
      setConfirming(false);
      setOpenId(null);
    }
    await reload();
    setBusy(false);
  }

  async function resolveFlag(item, resolution) {
    const result = await api.modResolveFlag(item.evidence.id, resolution);
    if (result?.error) setError(result.message);
    await reload();
  }

  const openItem = queue?.find((item) => item.id === openId) ?? null;
  const cannedLines = openItem
    ? VERDICTS.map((v) => copy.verdicts[v.key]?.subtext).filter(Boolean)
    : [];

  return (
    <main style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 class="headline headline-rule" style={{ fontSize: '1rem' }}>
        Analysis Queue
        <span class="dim" style={{ marginLeft: 'auto', fontFamily: 'var(--font-num)' }}>
          {queue === null ? '…' : `${queue.length} pending`}
        </span>
      </h1>

      {error && (
        <div class="verdict-banner sev-red">
          <div class="verdict-chip">!</div>
          <div><p class="subtext">{error}</p></div>
        </div>
      )}

      {queue === null ? (
        <p class="dim">Opening the queue…</p>
      ) : queue.length === 0 ? (
        <p class="dim">Queue is clear. Nothing awaiting review.</p>
      ) : (
        <div class="panel" style={{ padding: '4px 16px' }}>
          {queue.map((item) => (
            <div
              key={item.id}
              class="list-row"
              style={{ cursor: 'pointer' }}
              onClick={() => open(item)}
            >
              <img
                src={item.evidence.photo_url}
                alt=""
                loading="lazy"
                style={{ width: 44, height: 44, flex: 'none', objectFit: 'cover', borderRadius: 'var(--radius)' }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.85rem' }}>
                  #{item.riddle.sort_order} — {item.player.display_name}
                </div>
                <div class="dim" style={{ fontSize: '0.75rem' }}>{ago(item.created_at)}</div>
              </div>
              {item.flag && (
                <span class="dim" style={{ fontSize: '0.7rem', fontFamily: 'var(--font-head)', letterSpacing: '0.1em', color: 'var(--alert)' }}>
                  ⚠ SHARED?
                </span>
              )}
              {item.claimed_by && (
                <span class="dim" style={{ fontSize: '0.7rem', fontFamily: 'var(--font-head)', letterSpacing: '0.1em', color: 'var(--amber)' }}>
                  {item.claimed_by.label.toUpperCase()} IS VIEWING
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {openItem && (
        <section>
          <div style={{ position: 'relative', marginBottom: 12 }}>
            <img
              src={openItem.evidence.photo_url}
              alt="Submission photo"
              style={{ width: '100%', borderRadius: 'var(--radius)', display: 'block' }}
            />
          </div>
          <div class="panel" style={{ borderLeft: '3px solid var(--green)', marginBottom: 12, padding: '10px 14px' }}>
            <div class="dim" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--green)' }}>
              Riddle #{openItem.riddle.sort_order} — {openItem.player.display_name} submitted
            </div>
            <div style={{ marginTop: 4 }}>{openItem.riddle.text}</div>
          </div>

          {openItem.flag && (
            <div class="verdict-banner sev-red" style={{ marginBottom: 12 }}>
              <div class="verdict-chip">⚠</div>
              <div style={{ flex: 1 }}>
                <div class="verdict-headline">Possible shared photo</div>
                <p class="subtext" style={{ marginTop: 6 }}>
                  Near-duplicate of another team's evidence
                  (distance {openItem.flag.distance}).
                </p>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button class="btn secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem' }}
                          onClick={() => resolveFlag(openItem, 'cleared')}>
                    Clear flag
                  </button>
                  <button class="btn secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem', color: 'var(--alert)', borderColor: 'var(--alert)' }}
                          onClick={() => resolveFlag(openItem, 'confirmed')}>
                    Confirm duplicate
                  </button>
                </div>
              </div>
            </div>
          )}

          <button
            class="btn"
            style={{ background: 'var(--green)', marginBottom: 8 }}
            disabled={busy}
            onClick={() => sendVerdict(openItem, 'verified')}
          >
            ✓ Riddle Solved
          </button>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 8 }}>
            {VERDICTS.filter((v) => v.secondary).map((v) => (
              <button
                key={v.key}
                class="btn secondary"
                style={{ color: 'var(--amber)', borderColor: 'var(--amber)', padding: '10px 4px', fontSize: '0.7rem' }}
                disabled={busy}
                onClick={() => sendVerdict(openItem, v.key)}
              >
                {v.label}
              </button>
            ))}
          </div>
          <button
            class="btn secondary"
            style={{ color: 'var(--alert)', borderColor: 'var(--alert)', marginBottom: 14 }}
            disabled={busy}
            onClick={() => sendVerdict(openItem, 'not_found')}
          >
            Subject Not Found
          </button>

          <div class="field">
            <label for="flavor">
              Flavor text <span class="dim">(optional — canned line or custom)</span>
            </label>
            <input
              type="text"
              id="flavor"
              value={flavor}
              onInput={(e) => setFlavor(e.target.value)}
              maxLength={280}
              placeholder={cannedLines[0] ?? ''}
            />
          </div>
          {cannedLines.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 }}>
              {cannedLines.map((line) => (
                <button
                  key={line}
                  class="btn secondary"
                  style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem', textAlign: 'left', textTransform: 'none', letterSpacing: 0 }}
                  onClick={() => setFlavor(line)}
                >
                  {line}
                </button>
              ))}
            </div>
          )}

          {/* Player history (mocks/moderator.html): consistency of
              judgment — verdicts so far, and the derived strike state
              (ADR 0001: there is no stored level to display, only the
              non-reversed strike rows). */}
          {history && (
            <section style={{ borderTop: '1px dashed var(--border-dim)', marginTop: 14, paddingTop: 10 }}>
              <h2 class="headline headline-rule" style={{ fontSize: '0.8rem', marginBottom: 6 }}>
                {openItem.player.display_name} — History
              </h2>
              <div class="panel" style={{ padding: '4px 16px' }}>
                {history.submissions.slice(0, 5).map((s) => (
                  <div key={s.id} class="list-row" style={{ fontSize: '0.8rem' }}>
                    <span style={{ color: s.status === 'verified' ? 'var(--green)' : 'var(--amber)' }}>
                      {s.status === 'verified' ? '✓' : '!'}
                    </span>
                    <div style={{ flex: 1 }}>
                      Riddle #{s.riddle.sort_order} — {s.status}{' '}
                      <span class="dim">· {ago(s.created_at)}</span>
                    </div>
                  </div>
                ))}
                <div class="list-row" style={{ fontSize: '0.8rem' }}>
                  <span class="icon-chip" style={{ width: 24, height: 24, fontSize: '0.7rem' }}>⛨</span>
                  <div style={{ flex: 1 }}>
                    {history.strikes.filter((s) => !s.reversed_at).length === 0 ? (
                      <>Strikes: <b>none</b> <span class="dim">— clean record</span></>
                    ) : (
                      <>
                        Strikes:{' '}
                        <b style={{ color: 'var(--alert)' }}>
                          {history.strikes.filter((s) => !s.reversed_at).length} active
                        </b>
                        {history.strikes.map((s) => (
                          <div key={s.id} class="dim" style={{ fontSize: '0.72rem' }}>
                            Level {s.level}
                            {s.cooldown_until ? ` · cooldown to ${new Date(s.cooldown_until * 1000).toLocaleTimeString()}` : ''}
                            {s.reversed_at ? ' · reversed' : ''}
                            {s.note ? ` · “${s.note}”` : ''}
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Conduct: INAPPROPRIATE — visually separated, danger-styled
              (mocks/moderator.html). Issues verdict + strike in one
              action; copy stays plain by rule. */}
          <section style={{ borderTop: '1px dashed var(--border-dim)', marginTop: 14, paddingTop: 14 }}>
            {confirming ? (
              <>
                <button
                  class="btn danger"
                  disabled={busy}
                  onClick={() => sendInappropriate(openItem)}
                >
                  Confirm: remove photo and issue strike
                </button>
                <button
                  class="btn secondary"
                  style={{ marginTop: 8 }}
                  disabled={busy}
                  onClick={() => setConfirming(false)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <button class="btn danger" onClick={() => setConfirming(true)}>
                ⚠ Flag Inappropriate — issue strike
              </button>
            )}
            <p class="dim" style={{ fontSize: '0.75rem', marginTop: 6, textAlign: 'center' }}>
              Removes the photo, issues the next strike level. Plain notice to
              the player — no game flavor.
            </p>
          </section>
        </section>
      )}
    </main>
  );
}
