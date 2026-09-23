// Riddle list — the home tab and the emotional center of the app
// (ui.md: "the Batcomputer tile grid is the emotional center").
//
// Renders entirely from the snapshot: one tile per riddle, with the
// collapsed tile state (unsolved / pending / verified) driving the
// glyph and border. The progress strip above mirrors the same states.
export function RiddleListScreen({ snapshot, copy, onOpenRiddle }) {
  const riddles = snapshot.riddles;
  const solved = riddles.filter((r) => r.state === 'verified').length;

  return (
    <main style={{ flex: 1 }}>
      <h1 class="headline headline-rule" style={{ padding: '16px 16px 12px', fontSize: '0.95rem' }}>
        {copy.screens.riddles.headline}
        <span class="dim" style={{ marginLeft: 'auto', fontFamily: 'var(--font-num)', letterSpacing: 0 }}>
          {solved}/{riddles.length}
        </span>
      </h1>

      {/* The solved count is already in the heading; the strip is decoration. */}
      <div class="progress-strip" aria-hidden="true" style={{ marginBottom: 8 }}>
        {riddles.map((r) => (
          <span
            key={r.id}
            class={`seg ${r.state === 'verified' ? 'done' : r.state === 'pending' ? 'pending' : ''}`}
          />
        ))}
      </div>

      {riddles.length === 0 ? (
        <p class="dim" style={{ padding: 16 }}>{copy.screens.riddles.empty}</p>
      ) : (
        <div class="tile-grid">
          {riddles.map((r) => (
            <button
              key={r.id}
              type="button"
              class={`tile ${r.state === 'verified' ? 'solved' : r.state === 'pending' ? 'scanning' : ''}`}
              title={r.text}
              aria-label={copy.screens.riddles.tile(r.state, r.text)}
              onClick={() => onOpenRiddle(r.id)}
            >
              <span class="glyph-q" aria-hidden="true">{copy.tiles.unsolvedGlyph}</span>
            </button>
          ))}
        </div>
      )}
    </main>
  );
}
