// What a player may see of each drawer photo (ADR 0040).
//
// Drew's rules: a photo waiting for a moderator shows as its blurhash
// under the scanning effect, wherever it appears; a photo flagged
// inappropriate is only ever its blurhash to players; a rejected photo is
// shown as itself with a distinct border. The drawer says which photos are
// flagged; the snapshot's submissions (newest first) say the rest.

// Soft rejections: the photo did not answer the riddle, and may be tried
// again elsewhere (ADR 0035 frees it).
const REJECTED = new Set(['obscured', 'not_found', 'too_small', 'misaligned']);

// Photo id → { status, riddle_id } of its latest submission.
export function latestSubmissionByPhoto(snapshot) {
  const latest = new Map();
  for (const s of snapshot?.submissions ?? []) {
    if (s.evidence_item_id && !latest.has(s.evidence_item_id)) latest.set(s.evidence_item_id, s);
  }
  return latest;
}

// 'flagged' | 'pending' | 'verified' | 'rejected' | 'free', and the riddle
// the latest submission went to.
export function photoState(item, latest) {
  if (item.quarantined) return { state: 'flagged', riddleId: latest.get(item.id)?.riddle_id ?? null };
  const sub = latest.get(item.id);
  if (!sub) return { state: 'free', riddleId: null };
  if (sub.status === 'pending') return { state: 'pending', riddleId: sub.riddle_id };
  if (sub.status === 'verified') return { state: 'verified', riddleId: sub.riddle_id };
  if (REJECTED.has(sub.status)) return { state: 'rejected', riddleId: sub.riddle_id };
  return { state: 'free', riddleId: sub.riddle_id };
}

// A riddle's number as the board shows it.
export function riddleNumber(snapshot, riddleId) {
  return (snapshot?.riddles ?? []).findIndex((r) => r.id === riddleId) + 1;
}
