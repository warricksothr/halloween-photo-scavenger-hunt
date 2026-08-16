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

export function RiddleDetailScreen({ snapshot, copy, riddleId, onBack, onOpenDrawer }) {
  const riddle = snapshot.riddles.find((r) => r.id === riddleId);
  // Snapshot submissions are newest-first (state.py ORDER BY created_at DESC).
  const history = snapshot.submissions.filter((s) => s.riddle_id === riddleId);
  const latest = history[0] ?? null;
  const restriction = snapshot.me.restriction;

  const [drawer, setDrawer] = useState(null); // null = loading
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [flagged, setFlagged] = useState(false);

  useEffect(() => {
    api.drawer().then((result) => {
      if (result.error) setError(result.message);
      else setDrawer(result);
    });
  }, []);

  if (!riddle) {
    // Riddle vanished from the snapshot (moderator edit) — retreat.
    onBack();
    return null;
  }

  async function onSubmit() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    const result = await api.submit(riddleId, selected);
    if (result?.error) {
      if (result.error === 'flagged_no_resubmit') {
        // Conduct surface: plain copy, no theme flavor.
        setFlagged(true);
      } else if (result.error === 'submission_pending') {
        // Lost the double-tap race — harmless; the refresh below turns
        // the tile pending. Tell the player nothing went wrong.
        setError(copy.screens.detail.alreadyScanning);
      } else {
        setError(result.message);
      }
    }
    await refresh();
    setBusy(false);
  }

  const c = copy.screens.detail;
  const pending = riddle.state === 'pending';
  const canSubmit =
    !pending && !flagged && !restriction.blocks_submissions && riddle.state !== 'verified';

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

      {flagged && (
        // Conduct verdict (INAPPROPRIATE) → no resubmission on this
        // riddle. Un-themed by rule; the strike flow (increment 8)
        // owns the full interstitial.
        <div class="verdict-banner sev-red">
          <div class="verdict-chip">!</div>
          <div>
            <div class="verdict-headline">Submission locked</div>
            <p class="subtext" style={{ marginTop: 6 }}>
              This riddle can no longer be submitted by your team.
            </p>
          </div>
        </div>
      )}

      {restriction.blocks_submissions && (
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
                {drawer.map((item) => (
                  <div
                    key={item.id}
                    class="tile"
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
                  </div>
                ))}
              </div>
              <button class="btn" disabled={!selected || busy} onClick={onSubmit}>
                {busy ? c.submitting : c.submit}
              </button>
            </>
          )}
        </section>
      )}
    </main>
  );
}
