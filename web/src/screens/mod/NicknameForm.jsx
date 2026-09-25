// The name players see on this moderator's verdicts (ADR 0045).
//
// The header shows the moderator's SSO name, which players never see. The
// nickname is the one they do, so the form says plainly which is which,
// and what players see when it is blank: no name at all. It folds away in
// the rail, because it is set once a night and the queue needs the room.
//
// Copy is plain and lives here, like the rest of the console chrome.
import { useEffect, useState } from 'preact/hooks';

import { api } from '../../api';

// The server's cap (mod.py NicknameBody), the same as a codename's.
export const NICKNAME_MAX = 40;

export function NicknameForm({ nickname, onSaved = () => {} }) {
  const [draft, setDraft] = useState(nickname ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  // A save elsewhere (another tab, a rejoin) arrives through the store;
  // show it rather than a stale draft.
  useEffect(() => setDraft(nickname ?? ''), [nickname]);

  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    const result = await api.modSetNickname(draft.trim());
    if (result?.error) {
      setError(result.message);
    } else {
      setDraft(result.nickname ?? '');
      setSaved(true);
      await onSaved(result.nickname);
    }
    setBusy(false);
  }

  const unchanged = draft.trim() === (nickname ?? '');
  return (
    <details class="mod-nickname">
      <summary>
        {nickname ? <>Players see you as <strong>{nickname}</strong></> : 'Players see no name for you'}
      </summary>
      <form onSubmit={save}>
        <div class="field">
          <label for="mod-nickname">
            Nickname <span class="dim">(shown to players on your verdicts)</span>
          </label>
          <input
            type="text"
            id="mod-nickname"
            value={draft}
            maxLength={NICKNAME_MAX}
            autocomplete="off"
            placeholder="e.g. Oracle"
            onInput={(e) => {
              setDraft(e.target.value);
              setSaved(false);
            }}
          />
        </div>
        <p class="dim">
          Leave it blank and players see no name. Your sign-in name is only
          ever shown to moderators and the host.
        </p>
        <button type="submit" class="btn secondary mod-btn-small" disabled={busy || unchanged}>
          {busy ? 'Saving…' : 'Save nickname'}
        </button>
        {saved && <p class="dim" role="status">Saved.</p>}
        {error && <p class="subtext" role="alert">{error}</p>}
      </form>
    </details>
  );
}
