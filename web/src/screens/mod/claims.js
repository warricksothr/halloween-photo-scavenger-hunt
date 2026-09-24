// How to read a soft claim (ADR 0002, ADR 0038).
//
// A claim is only a record of who opened an item last, and it never
// expires on the server. The console used to show every claim as
// "<name> IS VIEWING", including the moderator's own and ones left hours
// earlier on another device, so a moderator could not tell their own
// items from a colleague's, and an abandoned claim kept an item out of
// everyone else's automatic next pick.
//
// A claim counts as someone viewing now for CLAIM_FRESH_SECONDS after it
// was made. Reviewing one photo takes well under that; a claim older than
// that is somebody who wandered off.
export const CLAIM_FRESH_SECONDS = 10 * 60;

// 'mine' | 'viewing' (another moderator, fresh) | 'stale' (another, old) | null
export function claimState(item, moderatorId, now = Date.now() / 1000) {
  const claim = item.claimed_by;
  if (!claim) return null;
  if (moderatorId && claim.id === moderatorId) return 'mine';
  // A queue from an older server has no age; treat it as fresh rather
  // than hand the item to a second moderator.
  const at = claimedAt(claim);
  if (at == null) return 'viewing';
  return now - at <= CLAIM_FRESH_SECONDS ? 'viewing' : 'stale';
}

// When the claim was made, on this device's clock: api.modQueue turns the
// server's claim_age into claimed_at_local on receipt.
export function claimedAt(claim) {
  return claim.claimed_at_local ?? null;
}
