// Team screen — roster, invites, and identity (teams stretch).
//
// Follows docs/impl/mocks/team.html: team identity with rename, the
// roster (member + device label + last-seen — the same facts the
// moderator heuristics use), and the invite panel (single-use token,
// 10-minute TTL, revocable).
//
// The QR is rendered as a copyable link + a QR-code image from the
// public chart API? No — no external services on a party LAN night.
// The invite link is shown as text for sharing; phones in the room
// scan nothing fancy: the host reads the code aloud or the inviter
// shows the link for Nearby Share / AirDrop. (The design's QR story
// targets the join code; invites are short links of the same shape.)
import { useEffect, useState } from 'preact/hooks';

import { api } from '../api';
import { refresh } from '../store';

function ago(epochSeconds) {
  if (!epochSeconds) return 'never seen';
  const mins = Math.max(0, Math.round((Date.now() / 1000 - epochSeconds) / 60));
  if (mins < 1) return 'active now';
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)} h ${mins % 60} min ago`;
}

function countdown(expiresAt, now) {
  const secs = Math.max(0, expiresAt - now);
  return `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`;
}

export function TeamScreen({ snapshot, copy }) {
  const [team, setTeam] = useState(null); // null = loading
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  async function reload() {
    const result = await api.team();
    if (result.error) setError(result.message);
    else setTeam(result);
  }

  useEffect(() => { reload(); }, []);
  // The invite expiry countdown is display-only; a 1s ticker keeps the
  // mock's "expires in 07:41" honest without any server round-trips.
  useEffect(() => {
    const timer = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  async function onRename() {
    const name = nameDraft.trim();
    if (!name || busy) return;
    setBusy(true);
    const result = await api.renameTeam(name);
    if (result?.error) setError(result.message);
    else {
      setEditing(false);
      // The leaderboard shows the team name — resync the snapshot.
      await refresh();
      await reload();
    }
    setBusy(false);
  }

  async function onNewInvite() {
    if (busy) return;
    setBusy(true);
    const result = await api.createInvite();
    if (result?.error) setError(result.message);
    await reload();
    setBusy(false);
  }

  async function onRevoke(token) {
    if (busy) return;
    setBusy(true);
    const result = await api.revokeInvite(token);
    if (result?.error) setError(result.message);
    await reload();
    setBusy(false);
  }

  const c = copy.screens.team;
  const inviteLink = (token) =>
    `${window.location.origin}/t/${token}`;

  return (
    <main style={{ flex: 1, padding: '0 0 16px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '14px 16px 4px' }}>
        <h1 class="headline headline-rule" style={{ fontSize: '1rem' }}>{c.headline}</h1>
      </div>

      {error && (
        <div class="verdict-banner sev-red" style={{ margin: '8px 16px' }}>
          <div class="verdict-chip">!</div>
          <div><p class="subtext">{error}</p></div>
        </div>
      )}

      {team === null ? (
        <p class="dim" style={{ padding: '8px 16px' }}>{c.loading}</p>
      ) : (
        <>
          {/* Identity + rename */}
          <section style={{ padding: '8px 16px' }}>
            <div class="panel" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div class="icon-chip" style={{ width: 44, height: 44, fontSize: '1.2rem', color: 'var(--green)' }}>⬡</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {editing ? (
                  <input
                    type="text"
                    value={nameDraft}
                    maxLength={40}
                    onInput={(e) => setNameDraft(e.target.value)}
                    style={{ width: '100%', marginBottom: 4 }}
                    placeholder={c.namePlaceholder}
                  />
                ) : (
                  <div style={{ fontFamily: 'var(--font-head)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                    {team.team.name ?? snapshot.me.display_name}
                  </div>
                )}
                <div class="dim" style={{ fontSize: '0.8rem' }}>
                  {team.members.length} / {team.team.size_limit} {c.operatives}
                </div>
              </div>
              {editing ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button class="btn secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem' }}
                          disabled={busy} onClick={onRename}>
                    {c.saveName}
                  </button>
                  <button class="btn secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem' }}
                          onClick={() => setEditing(false)}>
                    {c.cancel}
                  </button>
                </div>
              ) : (
                <button class="btn secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem' }}
                        onClick={() => { setNameDraft(team.team.name ?? ''); setEditing(true); }}>
                  {c.editName}
                </button>
              )}
            </div>
          </section>

          {/* Roster */}
          <section style={{ padding: '8px 16px' }}>
            <h2 class="headline headline-rule" style={{ fontSize: '0.85rem', marginBottom: 4 }}>{c.roster}</h2>
            <div class="panel" style={{ padding: '4px 16px' }}>
              {team.members.map((m) => (
                <div key={m.id} class="list-row">
                  <div class="icon-chip">{m.display_name[0].toUpperCase()}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div>
                      {m.display_name}
                      {m.you && <span class="dim" style={{ fontSize: '0.75rem' }}> {c.you}</span>}
                    </div>
                    <div class="dim" style={{ fontSize: '0.75rem' }}>
                      {m.device_label ? `${m.device_label} · ` : ''}{ago(m.last_seen_at)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Invites */}
          <section style={{ padding: '8px 16px' }}>
            <h2 class="headline headline-rule" style={{ fontSize: '0.85rem', marginBottom: 4 }}>{c.recruit}</h2>
            <div class="panel" style={{ padding: '12px 16px' }}>
              {team.members.length >= team.team.size_limit ? (
                <p class="dim" style={{ fontSize: '0.8rem' }}>{c.teamFull}</p>
              ) : (
                <>
                  {team.invites.map((inv) => (
                    <div key={inv.token} style={{ marginBottom: 12 }}>
                      <p class="subtext" style={{ wordBreak: 'break-all', fontFamily: 'var(--font-num)', fontSize: '0.8rem' }}>
                        {inviteLink(inv.token)}
                      </p>
                      <p class="dim" style={{ fontSize: '0.75rem', marginTop: 4 }}>
                        {c.singleUse} · {c.expiresIn}{' '}
                        <span style={{ fontFamily: 'var(--font-num)' }}>{countdown(inv.expires_at, now)}</span>
                      </p>
                      <button class="btn secondary"
                              style={{ width: 'auto', padding: '6px 12px', fontSize: '0.7rem', marginTop: 6, color: 'var(--alert)', borderColor: 'var(--alert)' }}
                              disabled={busy}
                              onClick={() => onRevoke(inv.token)}>
                        {c.revoke}
                      </button>
                    </div>
                  ))}
                  <button class="btn secondary" disabled={busy} onClick={onNewInvite}>
                    {team.invites.length ? c.newCode : c.createInvite}
                  </button>
                  <p class="dim" style={{ fontSize: '0.75rem', marginTop: 6 }}>{c.inviteNote}</p>
                </>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
