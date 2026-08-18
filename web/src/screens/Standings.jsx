// Standings screen — the leaderboard tab (increment 9).
//
// Follows docs/impl/mocks/standings.html, three variants:
// - live: ranked standings straight from the snapshot (score is a
//   server-side query, so the snapshot is always consistent — no
//   separate fetch, and SSE deltas already route to refresh()).
// - sealed: leaderboard_visibility = 'final-reveal' mid-round → the
//   snapshot's leaderboard is null and the tab shows the sealed note.
// - closed: the final standings + the recap timeline, fetched once from
//   GET /api/recap (players only after close; the timeline is the
//   audit log projected party-safe, ADR 0005).
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';

function hhmm(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit',
  });
}

// One recap entry → one themed line. The server ships facts (kind +
// fields); the theme pack owns the fiction (ADR 0005).
function recapLine(entry, recapCopy) {
  switch (entry.kind) {
    case 'opened': return recapCopy.opened(entry.operatives);
    case 'closed': return recapCopy.closed(entry.expired_pending);
    case 'first_solve': return recapCopy.firstSolve(entry);
    case 'lead_change': return recapCopy.leadChange(entry);
    case 'solve':
      return entry.mass_solve
        ? recapCopy.massSolve(entry)
        : recapCopy.solve(entry);
    default: return null;
  }
}

function StandingsList({ standings, you }) {
  return (
    <div class="panel" style={{ padding: '4px 16px' }}>
      {standings.map((row) => (
        <div
          key={row.team_id}
          class="list-row"
          style={row.you ? {
            background: 'rgba(127,212,232,0.06)',
            borderRadius: 'var(--radius)',
          } : undefined}
        >
          <span style={{
            fontFamily: 'var(--font-num)', width: 28,
            color: row.rank === 1 ? 'var(--green-bright)'
              : row.rank <= 3 ? 'var(--cyan)' : 'var(--text-dim)',
          }}>
            {String(row.rank).padStart(2, '0')}
          </span>
          <div style={{ flex: 1 }}>
            {row.team}
            {row.you && (
              <span class="dim" style={{ fontSize: '0.75rem' }}> {you}</span>
            )}
          </div>
          <span style={{
            fontFamily: 'var(--font-num)',
            color: row.rank === 1 ? 'var(--green-bright)'
              : row.rank <= 3 ? 'var(--cyan)' : 'var(--text-dim)',
          }}>
            {row.score}
          </span>
        </div>
      ))}
    </div>
  );
}

export function StandingsScreen({ snapshot, copy }) {
  const c = copy.screens.standings;
  const closed = snapshot.event.status === 'closed';
  const [recap, setRecap] = useState(null); // null = loading (closed only)

  useEffect(() => {
    if (closed) {
      api.recap().then((result) => {
        if (!result.error) setRecap(result);
      });
    }
  }, [closed]);

  // Closed: final standings + the night's timeline from /api/recap.
  if (closed) {
    if (recap === null) {
      return (
        <main style={{ flex: 1, padding: 16 }}>
          <p class="dim">Compiling the night's intel…</p>
        </main>
      );
    }
    const winner = recap.standings[0];
    return (
      <main style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div class="verdict-banner sev-green">
          <div class="verdict-chip">★</div>
          <div style={{ flex: 1 }}>
            <div class="verdict-headline headline-rule">{c.caseClosed}</div>
            <p class="subtext" style={{ marginTop: 6 }}>
              {winner
                ? c.caseClosedSubtext(winner.team, winner.score, recap.total_riddles)
                : 'Final standings are in.'}
            </p>
          </div>
        </div>

        <StandingsList standings={recap.standings} you={c.you} />

        <h2 class="headline headline-rule" style={{ fontSize: '0.85rem' }}>
          {c.recapHeadline}
        </h2>
        <div class="panel" style={{ padding: '4px 16px' }}>
          {recap.timeline.map((entry, i) => (
            <div key={i} class="list-row" style={{ fontSize: '0.85rem' }}>
              <span class="dim" style={{ fontFamily: 'var(--font-num)', width: 44 }}>
                {hhmm(entry.at)}
              </span>
              <div style={{ flex: 1 }}>{recapLine(entry, copy.recap)}</div>
            </div>
          ))}
        </div>
      </main>
    );
  }

  // Live or sealed.
  const standings = snapshot.leaderboard;
  return (
    <main style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h1 class="headline headline-rule" style={{ fontSize: '1rem' }}>{c.headline}</h1>
      {standings === null ? (
        <p class="dim">{c.sealed}</p>
      ) : standings.length === 0 ? (
        <p class="dim">{c.empty}</p>
      ) : (
        <StandingsList standings={standings} you={c.you} />
      )}
    </main>
  );
}
