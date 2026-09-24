// Team management (stretch; design.md moderation additions): the roster
// view with per-member removal behind an armed confirm. Copy stays plain
// by rule (conduct-adjacent surface; nothing themed).
import { ago } from './ago';

export function TeamsPanel({ teams, busy, confirmRemove, setConfirmRemove, onRemove }) {
  if (teams === null) return <p class="dim">Loading rosters…</p>;
  return (
    <div class="mod-teams-list">
      {teams.map((team) => (
        <div key={team.id} class="panel mod-list-panel">
          <div class="dim mod-team-head">
            {team.name ?? team.members[0]?.display_name ?? '(empty)'}
            {' · '}{team.members.length} / {team.size_limit}
            {team.open_invites > 0 && ` · ${team.open_invites} invite${team.open_invites > 1 ? 's' : ''} open`}
          </div>
          {team.members.map((member) => (
            <div key={member.id} class="list-row mod-small-row">
              <div style={{ flex: 1, minWidth: 0 }}>
                {member.display_name}
                <span class="dim" style={{ fontSize: '0.72rem' }}>
                  {' '}{member.device_label ? `${member.device_label} · ` : ''}{ago(member.last_seen_at ?? 0)}
                </span>
              </div>
              {confirmRemove?.member.id === member.id ? (
                <div style={{ display: 'flex', gap: 6 }}>
                  <button class="btn danger mod-btn-tiny" disabled={busy} onClick={onRemove}>
                    Confirm remove
                  </button>
                  <button class="btn secondary mod-btn-tiny" disabled={busy}
                          onClick={() => setConfirmRemove(null)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <button class="btn secondary mod-btn-tiny mod-btn-alert"
                        onClick={() => setConfirmRemove({ team, member })}>
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      ))}
      <p class="dim" style={{ fontSize: '0.72rem' }}>
        Removing a member parks them on their own team and revokes
        their sessions — their evidence stays with the old team.
        They can rejoin with the join code or a team invite.
      </p>
    </div>
  );
}
