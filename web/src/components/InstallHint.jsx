// The suggestion to install the app (TKT-01M390Y0VQ). install.js decides
// whether one applies; this renders it until the player dismisses it.
//
// A page reached from a link that carries a code (a join or invite QR)
// shows it even after an earlier "Not now" (ADR 0043): that is the moment
// joining in Safari would strand the player outside the app, and the
// hint's answer is to install, open the app and scan the same QR again.
import { useEffect, useState } from 'preact/hooks';

import {
  dismissHint,
  hintDismissed,
  installMode,
  onInstallAvailabilityChange,
  promptInstall,
} from '../install';

export function InstallHint({ copy, joinCode, fromLink = false }) {
  const [mode, setMode] = useState(() => installMode());
  const [hidden, setHidden] = useState(() => !fromLink && hintDismissed());

  // Chrome may offer the prompt after the screen has rendered.
  useEffect(() => onInstallAvailabilityChange(() => setMode(installMode())), []);

  if (hidden || mode === null || mode === 'installed') return null;
  const c = copy.screens.join.install;

  function dismiss() {
    dismissHint();
    setHidden(true);
  }

  return (
    <section class="panel install-hint" aria-labelledby="install-heading" style={{ padding: 16, marginBottom: 24 }}>
      <h2 id="install-heading" class="headline" style={{ fontSize: '0.9rem', marginBottom: 8 }}>
        {c.headline}
      </h2>
      {mode === 'ios' ? (
        <>
          <p style={{ marginBottom: 8 }}>{c.iosSteps}</p>
          <p class="dim">{c.iosThen(joinCode)}</p>
        </>
      ) : (
        <p>{c.promptBody}</p>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        {mode === 'prompt' && (
          <button type="button" class="btn" onClick={promptInstall}>{c.install}</button>
        )}
        <button type="button" class="btn secondary" onClick={dismiss}>{c.dismiss}</button>
      </div>
    </section>
  );
}
