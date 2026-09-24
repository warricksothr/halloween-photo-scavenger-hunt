// The pending queue: oldest first, with each item's flag and claim state.
// The open item is marked so the rail shows where the moderator is.
import { ago } from './ago';
import { claimState } from './claims';

export function QueueList({ queue, openId, onOpen, moderatorId = null }) {
  if (queue === null) return <p class="dim">Opening the queue…</p>;
  if (queue.length === 0) {
    return <p class="dim">Queue is clear. Nothing awaiting review.</p>;
  }
  return (
    <div class="panel mod-queue">
      {queue.map((item) => (
        <button
          key={item.id}
          type="button"
          class={`list-row mod-queue-row${item.id === openId ? ' is-open' : ''}`}
          aria-current={item.id === openId ? 'true' : undefined}
          onClick={() => onOpen(item)}
        >
          <img class="mod-thumb" src={item.evidence.photo_url} alt="" loading="lazy" />
          <span class="mod-queue-text">
            <span class="mod-queue-who">
              #{item.riddle.sort_order} — {item.player.display_name}
            </span>
            <span class="dim mod-queue-when">{ago(item.created_at)}</span>
          </span>
          <span class="mod-queue-tags">
            {item.flag && <span class="mod-tag mod-tag-alert">⚠ SHARED?</span>}
            <ClaimTag item={item} moderatorId={moderatorId} />
          </span>
        </button>
      ))}
    </div>
  );
}

// Your own claim, a colleague viewing now, or a claim left behind
// (ADR 0038).
function ClaimTag({ item, moderatorId }) {
  const state = claimState(item, moderatorId);
  if (state === 'mine') return <span class="mod-tag mod-tag-dim">OPENED BY YOU</span>;
  if (state === 'viewing') {
    return <span class="mod-tag mod-tag-amber">{item.claimed_by.label.toUpperCase()} IS VIEWING</span>;
  }
  if (state === 'stale') {
    return (
      <span class="mod-tag mod-tag-dim">
        {item.claimed_by.label.toUpperCase()} OPENED {ago(item.claimed_by.claimed_at).toUpperCase()}
      </span>
    );
  }
  return null;
}
