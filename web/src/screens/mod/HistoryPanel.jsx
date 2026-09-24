// Player history (mocks/moderator.html): consistency of judgment —
// verdicts so far, and the derived strike state (ADR 0001: there is no
// stored level to display, only the non-reversed strike rows).
import { ago } from './ago';

export function HistoryPanel({ player, history }) {
  const active = history.strikes.filter((s) => !s.reversed_at);
  return (
    <section class="mod-section">
      <h2 class="headline headline-rule mod-subhead">{player.display_name} — History</h2>
      <div class="panel mod-list-panel">
        {history.submissions.slice(0, 5).map((s) => (
          <div key={s.id} class="list-row mod-small-row">
            <span style={{ color: s.status === 'verified' ? 'var(--green)' : 'var(--amber)' }}>
              {s.status === 'verified' ? '✓' : '!'}
            </span>
            <div style={{ flex: 1 }}>
              Riddle #{s.riddle.sort_order} — {s.status}{' '}
              <span class="dim">· {ago(s.created_at)}</span>
            </div>
          </div>
        ))}
        <div class="list-row mod-small-row">
          <span class="icon-chip" style={{ width: 24, height: 24, fontSize: '0.7rem' }}>⛨</span>
          <div style={{ flex: 1 }}>
            {active.length === 0 ? (
              <>Strikes: <b>none</b> <span class="dim">— clean record</span></>
            ) : (
              <>
                Strikes: <b style={{ color: 'var(--alert)' }}>{active.length} active</b>
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
  );
}
