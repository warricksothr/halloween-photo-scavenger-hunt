// The moderation log (ADR 0044): the event's audit trail, newest first,
// one plain sentence a row. Moderators use it to review the calls made so
// far, their own and their colleagues', and to look at the photo behind
// any of them.
//
// Copy stays plain and lives here, not in the theme pack: the log is a
// conduct surface (strikes, removals), and conduct surfaces are never
// themed (design.md).
import { ago } from './ago';

// What the Moderation filter keeps: decisions a moderator or the host
// made about the game, plus the round's own open and close.
export const MODERATION_ACTIONS = new Set([
  'verdict.issued',
  'strike.issued',
  'strike.reversed',
  'evidence.quarantined',
  'duplicate_flag.raised',
  'duplicate_flag.resolved',
  'team.member_removed',
  'moderator.joined',
  'event.opened',
  'event.closed',
  'event.reopened',
]);

const VERDICTS = {
  verified: 'solved',
  obscured: 'obscured',
  too_small: 'too small',
  misaligned: 'misaligned',
  not_found: 'subject not found',
  inappropriate: 'inappropriate',
};

// "Batman (Team Gotham)", or just the one name when a team of one is
// labelled by its only member.
function who(about) {
  const { player, team } = about;
  if (player && team && team !== player) return `${player} (${team})`;
  return player ?? team ?? 'a player';
}

function riddle(about) {
  return about.riddle != null ? `Riddle #${about.riddle}` : 'a riddle';
}

// One row → { text, detail?, tone }. tone is 'good', 'warn', 'alert' or
// undefined, and only colours the marker.
export function logLine(row) {
  const a = row.about ?? {};
  const d = row.details ?? {};
  const actor = row.actor_name ?? row.actor_type;
  switch (row.action) {
    case 'verdict.issued': {
      const verdict = VERDICTS[d.verdict] ?? d.verdict;
      return {
        text: `${actor} marked ${who(a)}'s photo for ${riddle(a)} ${verdict}`,
        detail: d.flavor_text || undefined,
        tone: d.verdict === 'verified' ? 'good' : d.verdict === 'inappropriate' ? 'alert' : 'warn',
      };
    }
    case 'strike.issued':
      return {
        text: `${actor} gave ${who(a)} strike ${d.level}`,
        detail: [
          d.note ? `“${d.note}”` : null,
          d.cooldown_until
            ? `uploads paused until ${new Date(d.cooldown_until * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            : null,
        ].filter(Boolean).join(' · ') || undefined,
        tone: 'alert',
      };
    case 'strike.reversed':
      return { text: `${actor} reversed ${who(a)}'s strike ${d.original_level}`, detail: d.reason || undefined, tone: 'good' };
    case 'evidence.quarantined':
      return { text: `${actor} removed a photo from ${who(a)}'s drawer`, tone: 'alert' };
    case 'duplicate_flag.raised':
      return { text: `Possible duplicate: ${who(a)}'s photo looks like another team's`, tone: 'warn' };
    case 'duplicate_flag.resolved':
      return {
        text: `${actor} ${d.resolution === 'confirmed' ? 'confirmed' : 'cleared'} the duplicate flag on ${who(a)}'s photo`,
        tone: d.resolution === 'confirmed' ? 'alert' : 'good',
      };
    case 'team.member_removed':
      return { text: `${actor} removed ${a.player ?? 'a player'} from ${a.team ?? 'their team'}`, tone: 'alert' };
    case 'moderator.joined':
      return { text: `${a.moderator ?? actor} joined the console` };
    case 'event.opened':
      return { text: `${actor} opened the round` };
    case 'event.closed':
      return {
        text: `${actor} closed the round`,
        detail: d.expired_pending ? `${d.expired_pending} waiting scan${d.expired_pending === 1 ? '' : 's'} expired` : undefined,
      };
    case 'event.reopened':
      return { text: `${actor} reopened the round` };
    case 'event.created':
      return { text: `${actor} created the event` };
    case 'event.updated':
      return { text: `${actor} changed the event's settings` };
    case 'event.code_rotated':
      return { text: `${actor} replaced the ${d.code === 'mod' ? 'moderator' : 'join'} code` };
    case 'riddle.created':
      return { text: `${actor} added ${riddle(a)}` };
    case 'riddle.edited':
      return { text: `${actor} edited ${riddle(a)}` };
    case 'riddle.deleted':
      return { text: `${actor} deleted a riddle`, detail: d.text || undefined };
    case 'player.joined':
      return { text: `${who(a)} joined`, detail: d.device_label || undefined };
    case 'player.resumed':
      return { text: `${who(a)} rejoined`, detail: d.device_label || undefined };
    case 'session.revoked':
      return {
        text: d.reason === 'moderator'
          ? `${who(a)} was signed out by a moderator`
          : d.reason === 'switch' ? `${who(a)} switched teams` : `${who(a)} signed out`,
      };
    case 'evidence.uploaded':
      return { text: `${who(a)} took a photo` };
    case 'submission.created':
      return { text: `${who(a)} submitted a photo for ${riddle(a)}` };
    case 'notice.acknowledged':
      return { text: `${who(a)} acknowledged a strike notice` };
    case 'team_invite.created':
      return { text: `${actor} made an invite to ${a.team ?? 'their team'}` };
    case 'team_invite.redeemed':
      return { text: `${actor} joined ${a.team ?? 'a team'} by invite` };
    case 'team_invite.revoked':
      return { text: `${actor} withdrew an invite to ${a.team ?? 'their team'}` };
    case 'team.renamed':
      return { text: `${actor} renamed ${d.old_name ?? 'their team'} to ${d.new_name}` };
    default:
      return { text: `${actor}: ${row.action}` };
  }
}

function clock(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const TONES = { good: 'var(--green)', warn: 'var(--amber)', alert: 'var(--alert)' };

export function LogPanel({ rows, filter, setFilter, onZoom }) {
  if (rows === null) return <p class="dim">Loading the log…</p>;
  const shown = rows
    .filter((row) => filter === 'all' || MODERATION_ACTIONS.has(row.action))
    .slice()
    .reverse();
  return (
    <div class="mod-log">
      <div class="mod-switch" role="group" aria-label="Log filter">
        <button type="button" class="btn secondary mod-btn-small"
                aria-pressed={filter === 'moderation'} onClick={() => setFilter('moderation')}>
          Moderation
        </button>
        <button type="button" class="btn secondary mod-btn-small"
                aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
          Everything
        </button>
      </div>
      {shown.length === 0 ? (
        <p class="dim">Nothing logged yet.</p>
      ) : (
        <ol class="panel mod-list-panel mod-log-list" aria-label="Moderation log">
          {shown.map((row) => {
            const line = logLine(row);
            const photo = row.about?.evidence_id;
            return (
              <li key={row.id} class="list-row mod-small-row mod-log-row">
                <span class="mod-log-mark" aria-hidden="true"
                      style={{ background: TONES[line.tone] ?? 'var(--border-lit)' }} />
                <time class="dim mod-log-time" dateTime={new Date(row.created_at * 1000).toISOString()}
                      title={ago(row.created_at)}>
                  {clock(row.created_at)}
                </time>
                <div class="mod-log-text">
                  {line.text}
                  {line.detail && <div class="dim mod-log-detail">{line.detail}</div>}
                </div>
                {photo && (
                  <button type="button" class="btn secondary mod-btn-tiny"
                          onClick={() => onZoom({
                            src: `/api/mod/evidence/${photo}/photo`,
                            label: `Photo: ${line.text}`,
                          })}>
                    Photo
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
