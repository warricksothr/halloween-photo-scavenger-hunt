// Strike interstitial — the strike-1 warning (increment 8).
//
// Follows docs/impl/mocks/strike-interstitial.html exactly:
// - appears when the snapshot reports me.restriction.pending_notice
// - plain language, NO Arkham flavor — conduct surfaces are un-themed
//   by rule (design.md: "the player is told plainly"), so every string
//   here is hardcoded, never from the theme pack
// - acknowledging POSTs /api/me/notice-ack (logs notice.acknowledged)
// - uploads stay enabled after a strike-1 warning; level 2/3 surface
//   in the drawer's suspended variant instead
import { useState } from 'preact/hooks';

import { api } from '../api';
import { refresh } from '../store';

export function StrikeNoticeScreen() {
  const [busy, setBusy] = useState(false);

  async function acknowledge() {
    if (busy) return;
    setBusy(true);
    await api.noticeAck();
    // The ack is a mutation; the snapshot is the resync point
    // (ADR 0003) — refresh clears pending_notice and unmounts this.
    await refresh();
    setBusy(false);
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'grid', placeItems: 'center', padding: 24,
        background: 'rgba(0, 0, 0, 0.65)',
      }}
    >
      <div class="panel" style={{ border: '1px solid var(--alert)', maxWidth: 340 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <div class="verdict-chip" style={{ background: 'var(--alert)', color: 'var(--text)' }}>!</div>
          <div>
            <h1 class="verdict-headline" style={{ color: 'var(--alert)' }}>
              A submission was removed
            </h1>
            <p class="subtext" style={{ marginTop: 10 }}>
              One of your photos violated the event rules and was removed by a
              moderator. Repeated violations will restrict your ability to
              participate in this event.
            </p>
            <p class="dim" style={{ marginTop: 10, fontSize: '0.8rem' }}>
              This is a warning. You can keep playing — uploads are still enabled.
            </p>
          </div>
        </div>
        <button
          class="btn"
          style={{ marginTop: 16, background: 'var(--alert)', color: 'var(--text)' }}
          disabled={busy}
          onClick={acknowledge}
        >
          I understand
        </button>
        <p class="dim" style={{ textAlign: 'center', fontSize: '0.7rem', marginTop: 8 }}>
          Questions? Find the host — moderators can review or reverse strikes.
        </p>
      </div>
    </div>
  );
}
