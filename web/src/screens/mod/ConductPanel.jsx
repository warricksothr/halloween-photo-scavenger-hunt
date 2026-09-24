// Conduct: INAPPROPRIATE — visually separated, danger-styled
// (mocks/moderator.html). Issues verdict + strike in one action, behind
// an armed confirm; copy stays plain by rule (design.md: nothing themed
// ever touches a conduct surface).
export function ConductPanel({ busy, note, setNote, cooldown, setCooldown, confirming, setConfirming, onRemove }) {
  return (
    <section class="mod-section mod-conduct">
      <div class="field">
        <label for="strike-note">
          Note <span class="dim">(optional — recorded on the player's history)</span>
        </label>
        <input
          type="text"
          id="strike-note"
          value={note}
          onInput={(e) => setNote(e.target.value)}
          maxLength={280}
          placeholder="Why this photo was removed"
        />
      </div>
      <div class="field">
        <label for="strike-cooldown">
          Cooldown minutes <span class="dim">(strike 2 only — default 15)</span>
        </label>
        <input
          type="number"
          id="strike-cooldown"
          value={cooldown}
          onInput={(e) => setCooldown(e.target.value)}
          min={1}
          max={1440}
          inputMode="numeric"
        />
      </div>
      {confirming ? (
        <>
          <button class="btn danger" disabled={busy} onClick={onRemove}>
            Confirm: remove photo and issue strike
          </button>
          <button class="btn secondary" style={{ marginTop: 8 }} disabled={busy}
                  onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </>
      ) : (
        <button class="btn danger" onClick={() => setConfirming(true)}>
          ⚠ Flag Inappropriate — issue strike
        </button>
      )}
      <p class="dim mod-conduct-note">
        Removes the photo, issues the next strike level. Plain notice to
        the player — no game flavor.
      </p>
    </section>
  );
}
