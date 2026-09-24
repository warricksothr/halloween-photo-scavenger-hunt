// Riddle detail — one riddle, its verdict state, and the submit flow
// (increment 6).
//
// The screen renders entirely from the snapshot: the riddle's collapsed
// tile state plus this team's submission history for it. The one thing
// the snapshot does NOT carry is the drawer's photos, so those are
// fetched on mount (api.drawer) for the evidence picker.
//
// Conduct copy rule (design.md): flagged/restriction messages are
// un-themed by rule, so they are plain strings here — never in the
// theme pack, where flavor text could accidentally decorate a conduct
// surface.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';
import { refresh } from '../store';

// submission.status → banner severity. pending gets the cyan scan
// treatment; soft rejections are red/amber per THEME-NOTES.md.
const SEVERITY = {
  pending: 'sev-cyan',
  verified: 'sev-green',
  obscured: 'sev-red',
  not_found: 'sev-red',
  too_small: 'sev-red',
  misaligned: 'sev-amber',
  expired: 'sev-amber',
};

export function RiddleDetailScreen({
  snapshot, copy, riddleId, onBack, onOpenDrawer, onGone = onBack, initialSelected = null,
}) {
  const riddle = snapshot.riddles.find((r) => r.id === riddleId);
  const hints = riddle?.hints ?? [];
  // Snapshot submissions are newest-first (state.py ORDER BY created_at DESC).
  const history = snapshot.submissions.filter((s) => s.riddle_id === riddleId);
  const latest = history[0] ?? null;
  const restriction = snapshot.me.restriction;

  const [drawer, setDrawer] = useState(null); // null = loading
  // Seeded when the player comes back from taking a photo for this riddle
  // (ADR 0036), so the new photo is ready to submit.
  const [selected, setSelected] = useState(initialSelected);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // How many hint levels this player has asked to see, tagged with the
  // riddle it belongs to. Nothing shows until they ask: a hint the
  // player did not want is a spoiler, and the ladder is their escape
  // hatch, not part of the riddle text. Tagging the riddle means a
  // reused screen cannot render the next ladder from a stale count —
  // an effect would reset it only after that first render committed.
  const [reveal, setReveal] = useState({ riddleId, count: 0 });
  const revealed = reveal.riddleId === riddleId ? reveal.count : 0;

  useEffect(() => {
    api.drawer().then((result) => {
      if (result.error) setError(result.message);
      else setDrawer(result);
    });
  }, []);

  // One riddle per photo (ADR 0035): a photo pending or solved on a
  // riddle is shown but cannot be picked, labelled with the riddle's
  // number on the board. The server refuses it anyway; this says why
  // before the player tries.
  const inUse = photosInUse(snapshot);

  if (!riddle) {
    // Riddle vanished from the snapshot (moderator edit) — retreat
    // without a history step, since Back would only lead here again.
    onGone();
    return null;
  }

  async function onSubmit() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    const result = await api.submit(riddleId, selected);
    if (result?.error) {
      if (result.error === 'submission_pending') {
        // Lost the double-tap race — harmless; the refresh below turns
        // the tile pending. Tell the player nothing went wrong.
        setError(copy.screens.detail.alreadyScanning);
      } else if (result.error === 'evidence_in_use') {
        // A teammate used the photo since this drawer loaded; the refresh
        // below greys it out here too.
        setSelected(null);
        setError(copy.screens.detail.photoTaken(riddleNumber(snapshot, result.riddle_id)));
      } else {
        setError(result.message);
      }
    }
    await refresh();
    setBusy(false);
  }

  const c = copy.screens.detail;
  const pending = riddle.state === 'pending';
  // The snapshot's restriction is plain JSON — the derived-state
  // contract is level-based (api.md): 3 bans submissions, 2 gates
  // uploads only, so the detail screen checks level 3.
  const submissionsBanned = restriction?.level === 3;
  const canSubmit =
    !pending && !submissionsBanned && riddle.state !== 'verified';

  // The banner: pending shows SCANNING; otherwise the latest verdict.
  // A soft rejection's banner stays up until the next submission —
  // the player needs the "why" while they re-shoot.
  const bannerStatus = pending ? 'pending' : latest?.status;
  const banner = bannerStatus && copy.verdicts[bannerStatus];

  return (
    <main style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <button class="btn secondary" onClick={onBack} style={{ width: 'auto', padding: '8px 14px' }}>
        {c.back}
      </button>

      <h1 class="headline headline-rule" style={{ fontSize: '0.95rem' }}>
        {riddle.text}
      </h1>

      {banner && (
        <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius)' }}>
          <div class={`verdict-banner ${SEVERITY[bannerStatus] ?? 'sev-amber'}`}>
            <div class="verdict-chip">{bannerStatus === 'verified' ? '✓' : bannerStatus === 'pending' ? '…' : '!'}</div>
            <div>
              <div class="verdict-headline">{banner.headline}</div>
              <p class="subtext" style={{ marginTop: 6 }}>
                {latest?.verdict_flavor ?? banner.subtext}
              </p>
            </div>
          </div>
          {pending && <div class="scan-sweep" />}
        </div>
      )}

      {submissionsBanned && (
        <div class="verdict-banner sev-red">
          <div class="verdict-chip">!</div>
          <div>
            <div class="verdict-headline">Submissions paused</div>
            <p class="subtext" style={{ marginTop: 6 }}>
              Your ability to submit evidence is currently restricted.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div class="verdict-banner sev-amber">
          <div class="verdict-chip">!</div>
          <div><p class="subtext">{error}</p></div>
        </div>
      )}

      {hints.length > 0 && (
        <section>
          {revealed > 0 && (
            <ul class="hint-list">
              {hints.slice(0, revealed).map((hint, level) => (
                <li key={level} class="hint-item">
                  <span class="hint-level">L{level + 1}</span>
                  <span>{hint}</span>
                </li>
              ))}
            </ul>
          )}
          {revealed < hints.length ? (
            <button class="btn secondary" onClick={() => setReveal({ riddleId, count: revealed + 1 })}>
              {c.needNudge}
            </button>
          ) : (
            <p class="dim">{c.noMoreHints}</p>
          )}
        </section>
      )}

      {canSubmit && (
        <section>
          <h2 class="headline" style={{ fontSize: '0.8rem', marginBottom: 8 }}>{c.pickEvidence}</h2>
          {drawer === null ? (
            <p class="dim">{c.loading}</p>
          ) : drawer.length === 0 ? (
            <button class="btn secondary" onClick={onOpenDrawer}>{c.emptyDrawer}</button>
          ) : (
            <>
              <div class="tile-grid" style={{ padding: 0, marginBottom: 12 }}>
                {drawer.map((item, index) => {
                  const use = inUse.get(item.id);
                  const note = use && (use.status === 'pending'
                    ? c.inUsePending(riddleNumber(snapshot, use.riddle_id))
                    : c.inUseSolved(riddleNumber(snapshot, use.riddle_id)));
                  return (
                    <button
                      key={item.id}
                      type="button"
                      class={use ? `tile in-use ${use.status}` : 'tile'}
                      aria-label={note ? `${c.evidenceOption(index + 1)}, ${note}` : c.evidenceOption(index + 1)}
                      aria-pressed={selected === item.id}
                      disabled={Boolean(use)}
                      style={{
                        aspectRatio: '1',
                        borderColor: selected === item.id ? 'var(--cyan-bright)' : undefined,
                        borderWidth: selected === item.id ? 2 : undefined,
                      }}
                      onClick={() => setSelected(item.id)}
                    >
                      <img
                        src={item.photo_url}
                        alt=""
                        style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius)' }}
                        loading="lazy"
                      />
                      {note && <span class="in-use-label" aria-hidden="true">{note}</span>}
                    </button>
                  );
                })}
              </div>
              <button class="btn" disabled={!selected || busy} onClick={onSubmit}>
                {busy ? c.submitting : c.submit}
              </button>
              {/* A new shot is always an option, not only for an empty
                  drawer; the drawer brings the player back here with it
                  selected. */}
              <button class="btn secondary" onClick={onOpenDrawer} style={{ marginTop: 8 }}>
                {c.takeNew}
              </button>
            </>
          )}
        </section>
      )}
    </main>
  );
}

// Photo id → the submission holding it, for photos pending or solved on
// some riddle. Snapshot submissions are the team's, newest first, and a
// photo holds at most one such submission (ADR 0035).
function photosInUse(snapshot) {
  const held = new Map();
  for (const s of snapshot.submissions) {
    if ((s.status === 'pending' || s.status === 'verified') && s.evidence_item_id && !held.has(s.evidence_item_id)) {
      held.set(s.evidence_item_id, s);
    }
  }
  return held;
}

// A riddle's number as the board shows it: its position in the list.
function riddleNumber(snapshot, riddleId) {
  return snapshot.riddles.findIndex((r) => r.id === riddleId) + 1;
}
