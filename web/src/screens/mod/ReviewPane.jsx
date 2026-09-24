// The evidence under review: the riddle it answers and the photo, large.
// A "Shared?" item shows its photo beside the one it matched, so the
// moderator judges the duplicate by eye (ADR 0029). Each photo is a
// button that opens the full-size view.
export function ReviewPane({ item, onZoom }) {
  const flag = item.flag;
  return (
    <div class="mod-review-inner">
      <div class="panel mod-riddle">
        <div class="mod-riddle-label">
          Riddle #{item.riddle.sort_order} — {item.player.display_name} submitted
        </div>
        <div class="mod-riddle-text">{item.riddle.text}</div>
      </div>
      {flag?.other_photo_url ? (
        <div class="mod-compare">
          <Photo
            src={item.evidence.photo_url}
            caption={`This submission — ${item.player.display_name}`}
            label="Enlarge the submitted photo"
            onZoom={onZoom}
          />
          <Photo
            src={flag.other_photo_url}
            caption={`Matched — ${flag.other_team_label ?? 'another team'}`
              + ` · distance ${flag.distance}`}
            label="Enlarge the matched photo"
            onZoom={onZoom}
            alert
          />
        </div>
      ) : (
        <Photo
          src={item.evidence.photo_url}
          label="Enlarge the submitted photo"
          onZoom={onZoom}
          single
        />
      )}
    </div>
  );
}

function Photo({ src, caption, label, onZoom, alert = false, single = false }) {
  return (
    <figure class={`mod-photo${single ? ' is-single' : ''}${alert ? ' is-alert' : ''}`}>
      <button
        type="button"
        class="mod-photo-button"
        aria-label={label}
        onClick={() => onZoom({ src, label: caption ?? 'Submission photo' })}
      >
        <img src={src} alt={caption ?? 'Submission photo'} />
      </button>
      {caption && <figcaption class="dim">{caption}</figcaption>}
    </figure>
  );
}
