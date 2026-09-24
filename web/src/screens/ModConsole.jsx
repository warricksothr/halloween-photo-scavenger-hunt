// Moderator console — the queue (increment 7), laid out per screen size
// (ADR 0029).
//
// Content follows docs/impl/mocks/moderator.html: a work queue, not the
// game — queue list (oldest first, claim state, flag badge), the open
// item's photo with the riddle it answers, one-tap verdicts, an optional
// flavor line, the player's history, and the separated conduct action.
// A phone stacks all of that in one column, as it always has; a tablet
// puts the queue in a rail beside the review; a desktop gives the queue,
// the photo, and the decision a column each (mod-console.css).
//
// Concurrency is the server's (ADR 0002): a lost verdict race comes
// back 409 and the queue refetches; the claim is advisory and shown to
// other moderators, never a lock. Queue freshness comes from the
// store's SSE stream: submission_new and queue_resolved deltas trigger
// a refetch — no polling.
import { useCallback, useEffect, useState } from 'preact/hooks';

import '../mod-console.css';
import { api } from '../api';
import { subscribeDeltas } from '../store';
import { ConductPanel } from './mod/ConductPanel';
import { DecisionPanel } from './mod/DecisionPanel';
import { HistoryPanel } from './mod/HistoryPanel';
import { Lightbox } from './mod/Lightbox';
import { QueueList } from './mod/QueueList';
import { ReviewPane } from './mod/ReviewPane';
import { TeamsPanel } from './mod/TeamsPanel';

// The verdicts whose theme-pack subtext offers canned flavor lines.
const VERDICT_KEYS = ['verified', 'obscured', 'too_small', 'misaligned', 'not_found'];

// The next item to open after a decision: the oldest pending one that no
// other moderator is viewing. Auto-advance must not walk this moderator
// into someone else's claim (ADR 0002: claims are advisory, but they are
// how two moderators avoid judging the same photo twice).
export function nextToReview(queue, resolvedId, moderatorId) {
  return (
    queue.find(
      (item) =>
        item.id !== resolvedId &&
        (!item.claimed_by || item.claimed_by.id === moderatorId),
    ) ?? null
  );
}

export function ModConsoleScreen({ copy, moderatorId = null }) {
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
  // Team management (stretch): the rosters, one switch away from the queue.
  // Removal is a danger action — same armed-confirm pattern as
  // INAPPROPRIATE — and copy stays plain by rule (conduct-adjacent
  // surface; nothing themed).
  const [teams, setTeams] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null); // {team, member}
  // Conduct inputs for the INAPPROPRIATE action. The backend accepts a
  // note and a strike-2 cooldown window, so the moderator sets them here
  // instead of sending an empty default. Labels stay plain by rule.
  const [note, setNote] = useState('');
  const [cooldown, setCooldown] = useState('15');
  // The rail shows the queue or the team rosters; on a wide screen the
  // rosters take the main area, so the two never compete for space.
  const [view, setView] = useState('queue');
  const [zoom, setZoom] = useState(null); // { src, label } of the full-size photo
  const closeZoom = useCallback(() => setZoom(null), []);

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
    return result;
  }

  // After a decision, move straight to the next submission (ADR 0029), or
  // show the empty state when nothing is left that is free to review.
  async function advance(resolvedId) {
    const fresh = await reload();
    const next = fresh ? nextToReview(fresh, resolvedId, moderatorId) : null;
    if (next) open(next);
    else setOpenId(null);
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
    setView('queue');
    setOpenId(item.id);
    setError(null);
    setConfirming(false);
    setHistory(null);
    setNote('');
    setCooldown('15');
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
      await reload();
    } else {
      setFlavor('');
      await advance(item.id);
    }
    setBusy(false);
  }

  async function sendInappropriate(item) {
    if (busy) return;
    // The server takes cooldown_minutes only for strike 2 (default 15) and
    // 422s outside 1–1440, so an out-of-range entry is caught here rather
    // than sent. An empty field means "use the default".
    const minutes = cooldown.trim() === '' ? null : Number(cooldown);
    if (minutes !== null
        && (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440)) {
      setError('Cooldown must be a whole number of minutes between 1 and 1440.');
      return;
    }
    setBusy(true);
    setError(null);
    // Conduct copy is plain and hardcoded here by rule (design.md):
    // nothing themed ever touches a conduct surface.
    const result = await api.modInappropriate(item.id, note.trim(), minutes);
    if (result?.error) {
      if (result.error !== 'already_resolved') setError(result.message);
      await reload();
    } else {
      setConfirming(false);
      setNote('');
      setCooldown('15');
      await advance(item.id);
    }
    setBusy(false);
  }

  async function resolveFlag(item, resolution) {
    const result = await api.modResolveFlag(item.evidence.id, resolution);
    if (result?.error) setError(result.message);
    await reload();
  }

  async function loadTeams() {
    const result = await api.modTeams();
    if (result.error) setError(result.message);
    else setTeams(result.teams);
  }

  function showView(next) {
    setView(next);
    setConfirmRemove(null);
    // Load on open only — membership changes are deliberate moderator
    // acts, not a stream; there is no SSE delta for them.
    if (next === 'teams' && teams === null) loadTeams();
  }

  async function removeMember() {
    if (busy || !confirmRemove) return;
    setBusy(true);
    setError(null);
    const { team, member } = confirmRemove;
    const result = await api.modRemoveMember(team.id, member.id);
    if (result?.error) setError(result.message);
    else setConfirmRemove(null);
    await loadTeams();
    setBusy(false);
  }

  const openItem = queue?.find((item) => item.id === openId) ?? null;
  const cannedLines = openItem
    ? VERDICT_KEYS.map((key) => copy.verdicts[key]?.subtext).filter(Boolean)
    : [];

  return (
    <main class="mod-console">
      <aside class="mod-rail">
        <h1 class="headline headline-rule mod-title">
          Analysis Queue
          <span class="dim mod-count">
            {queue === null ? '…' : `${queue.length} pending`}
          </span>
        </h1>
        <div class="mod-switch" role="group" aria-label="Console view">
          <button type="button" class="btn secondary mod-btn-small"
                  aria-pressed={view === 'queue'} onClick={() => showView('queue')}>
            Queue
          </button>
          <button type="button" class="btn secondary mod-btn-small"
                  aria-pressed={view === 'teams'} onClick={() => showView('teams')}>
            Teams
          </button>
        </div>
        {error && (
          <div class="verdict-banner sev-red">
            <div class="verdict-chip">!</div>
            <div><p class="subtext">{error}</p></div>
          </div>
        )}
        <QueueList queue={queue} openId={openId} onOpen={open} />
      </aside>

      {view === 'teams' ? (
        <section class="mod-main" aria-label="Team rosters">
          <TeamsPanel
            teams={teams}
            busy={busy}
            confirmRemove={confirmRemove}
            setConfirmRemove={setConfirmRemove}
            onRemove={removeMember}
          />
        </section>
      ) : openItem ? (
        <div class="mod-detail">
          <section class="mod-review" aria-label="Submission">
            <ReviewPane item={openItem} onZoom={setZoom} />
          </section>
          <section class="mod-decide" aria-label="Decision">
            <DecisionPanel
              item={openItem}
              busy={busy}
              flavor={flavor}
              setFlavor={setFlavor}
              cannedLines={cannedLines}
              onVerdict={sendVerdict}
              onResolveFlag={resolveFlag}
            />
            {history && <HistoryPanel player={openItem.player} history={history} />}
            <ConductPanel
              busy={busy}
              note={note}
              setNote={setNote}
              cooldown={cooldown}
              setCooldown={setCooldown}
              confirming={confirming}
              setConfirming={setConfirming}
              onRemove={() => sendInappropriate(openItem)}
            />
          </section>
        </div>
      ) : (
        <section class="mod-main mod-placeholder">
          <p class="dim">
            {queue?.length ? 'Pick a submission from the queue.' : 'Nothing to review right now.'}
          </p>
        </section>
      )}

      {zoom && <Lightbox photo={zoom} onClose={closeZoom} />}
    </main>
  );
}
