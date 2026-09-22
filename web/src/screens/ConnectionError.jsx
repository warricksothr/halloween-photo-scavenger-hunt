// The connection-error screen. Un-themed by rule (like the strike
// interstitial): it renders before any theme copy has loaded, so it carries
// its own plain copy. The retry button re-enters boot via store.retry().
export function ConnectionErrorScreen({ message, onRetry }) {
  return (
    <div class="frame">
      <main style={{ padding: 16 }}>
        <div class="verdict-banner sev-red">
          <div class="verdict-chip">!</div>
          <div>
            <div class="verdict-headline">Connection Failed</div>
            <p class="subtext" style={{ marginTop: 6 }}>{message}</p>
          </div>
        </div>
        <button class="btn" type="button" onClick={onRetry}>Try again</button>
      </main>
    </div>
  );
}
