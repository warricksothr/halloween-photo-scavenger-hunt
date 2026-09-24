// The pending queue: oldest first, with each item's flag and claim state.
// The open item is marked so the rail shows where the moderator is.
import { ago } from './ago';

export function QueueList({ queue, openId, onOpen }) {
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
            {item.claimed_by && (
              <span class="mod-tag mod-tag-amber">
                {item.claimed_by.label.toUpperCase()} IS VIEWING
              </span>
            )}
          </span>
        </button>
      ))}
    </div>
  );
}
