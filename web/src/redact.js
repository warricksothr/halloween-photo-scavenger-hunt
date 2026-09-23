// Path redaction, the browser mirror of server/app/logging.py.
//
// Join codes, moderator codes and invite tokens live in the URL, and both
// the request log and error reports must not carry them. The SPA links
// (/j, /m, /t) are here for the same reason the server lists them: a QR
// link hits the app directly, so its path leaks in a breadcrumb the same
// way an API path does.
export const REDACTED = '<redacted>';

const CODE_PREFIXES = ['/api/join', '/api/mod/join', '/api/team/invites', '/j', '/m', '/t'];

// Replace the bearer segment after a code-carrying prefix. Matched by
// prefix, not exact route: an unexpected suffix must still redact the
// credential rather than leak it.
export function redactPath(path) {
  if (typeof path !== 'string') return path;
  for (const prefix of CODE_PREFIXES) {
    if (!path.startsWith(`${prefix}/`)) continue;
    const rest = path.slice(prefix.length + 1);
    const slash = rest.indexOf('/');
    const credential = slash === -1 ? rest : rest.slice(0, slash);
    const suffix = slash === -1 ? '' : rest.slice(slash);
    if (!credential) return path;
    return `${prefix}/${REDACTED}${suffix}`;
  }
  return path;
}
