// Riddle list — the home tab and the emotional center of the app
// (ui.md: "the Batcomputer tile grid is the emotional center").
//
// Renders entirely from the snapshot: one tile per riddle, with the
// collapsed tile state (unsolved / pending / verified) driving the
// glyph and border. The progress strip above mirrors the same states.
export function RiddleListScreen({ snapshot, copy }) {
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

      <div class="progress-strip" style={{ marginBottom: 8 }}>
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
            <div
              key={r.id}
              class={`tile ${r.state === 'verified' ? 'solved' : r.state === 'pending' ? 'scanning' : ''}`}
              title={r.text}
            >
              <span class="glyph-q">{copy.tiles.unsolvedGlyph}</span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
