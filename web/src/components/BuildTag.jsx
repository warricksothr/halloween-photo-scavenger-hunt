// The web build id, in small print at the foot of a screen (ADR 0041), so
// whoever holds the phone can say which build they are on. Only the
// client's own id: it is already public in the bundle, whereas the
// server's release stays behind admin sign-in.
import { WEB_BUILD } from '../version';

export function BuildTag({ build = WEB_BUILD }) {
  return <p class="build-tag">Build {build}</p>;
}
