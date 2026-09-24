// The decision: the duplicate flag's actions (when there is one), the
// one-tap verdicts in the mock's order and severity, and the optional
// flavor line from the theme pack's verdict bank.
export function DecisionPanel({ item, busy, flavor, setFlavor, cannedLines, onVerdict, onResolveFlag }) {
  return (
    <div class="mod-decision">
      {item.flag && (
        <div class="verdict-banner sev-red">
          <div class="verdict-chip">⚠</div>
          <div style={{ flex: 1 }}>
            <div class="verdict-headline">Possible shared photo</div>
            <p class="subtext" style={{ marginTop: 6 }}>
              Near-duplicate of another team's evidence
              (distance {item.flag.distance}).
            </p>
            <div class="mod-flag-actions">
              <button class="btn secondary mod-btn-small" onClick={() => onResolveFlag(item, 'cleared')}>
                Clear flag
              </button>
              <button class="btn secondary mod-btn-small mod-btn-alert"
                      onClick={() => onResolveFlag(item, 'confirmed')}>
                Confirm duplicate
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        class="btn"
        style={{ background: 'var(--green)' }}
        disabled={busy}
        onClick={() => onVerdict(item, 'verified')}
      >
        ✓ Riddle Solved
      </button>
      <div class="mod-retry-grid">
        {[
          ['obscured', 'Obscured'],
          ['too_small', 'Too Small'],
          ['misaligned', 'Misaligned'],
        ].map(([key, label]) => (
          <button
            key={key}
            class="btn secondary mod-btn-amber"
            disabled={busy}
            onClick={() => onVerdict(item, key)}
          >
            {label}
          </button>
        ))}
      </div>
      <button
        class="btn secondary mod-btn-alert"
        disabled={busy}
        onClick={() => onVerdict(item, 'not_found')}
      >
        Subject Not Found
      </button>

      <div class="field">
        <label for="flavor">
          Flavor text <span class="dim">(optional — canned line or custom)</span>
        </label>
        <input
          type="text"
          id="flavor"
          value={flavor}
          onInput={(e) => setFlavor(e.target.value)}
          maxLength={280}
          placeholder={cannedLines[0] ?? ''}
        />
      </div>
      {cannedLines.length > 0 && (
        <div class="mod-canned">
          {cannedLines.map((line) => (
            <button key={line} class="btn secondary mod-canned-line" onClick={() => setFlavor(line)}>
              {line}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
