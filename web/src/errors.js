// Error reporting to GlitchTip (Sentry ingest protocol), from the browser.
//
// Two things shape this module. First, it is inert: with no
// VITE_ERROR_DSN the dynamic import never happens, so @sentry/browser is
// not in the entry bundle and nothing is reported. Second, the app keeps
// credentials in the URL — /j/<code>, /m/<code>, /t/<token> and the API
// equivalents — so the same path redaction the server uses runs on every
// event, transaction and breadcrumb on the way out (ADR 0017).
//
// The last request id from a response header is attached as a tag, which
// is what ties a browser error to its line in the server log (ADR 0016).
import { redactPath } from './redact';

const DSN = import.meta.env.VITE_ERROR_DSN;
const TRACES_SAMPLE_RATE = Number(
  import.meta.env.VITE_TRACES_SAMPLE_RATE ?? '0.1',
);
const ENVIRONMENT = import.meta.env.VITE_ERROR_ENVIRONMENT || undefined;
const RELEASE = import.meta.env.VITE_ERROR_RELEASE || undefined;

const DROPPED_REQUEST_KEYS = ['headers', 'cookies', 'data', 'env', 'query_string'];
const URL_DATA_KEYS = new Set(['url', 'http.url', 'http.query', 'http.fragment']);

let lastRequestId = null;
let sentry = null;
let started = false;

// api.js clears the id as a request begins and records the response id on
// the way back, so a request that never got headers (a network failure)
// reports with no id rather than the previous request's — the tag is a
// correlation, and a wrong one is worse than none.
export function beginRequest() {
  lastRequestId = null;
}

// api.js records the header here; the tag reads it at send time, so an
// event carries the id of the request that was in flight when it fired.
// An absent header clears the id: the identity of this response is
// unknown, and the previous request's id must not stand in for it.
export function recordRequestId(id) {
  lastRequestId = id || null;
}

export function lastRequestIdForTest() {
  return lastRequestId;
}

const ABSOLUTE_URL = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^/]*/;

// A path-like or URL-like run inside free text — quoted, key-prefixed, or
// on its own line — so the credential is not hidden by surrounding prose
// or punctuation. The run ends at whitespace; sentence punctuation that
// closes a quote or bracket is peeled back before redaction.
const URL_IN_TEXT = /[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^\s]+|\/[^\s]*/g;
const TRAILING_PUNCTUATION = /['"`)\]}>,.;:!?]+$/;

function scrubUrl(value) {
  if (typeof value !== 'string' || value === '') return value;
  // Split the path off any absolute URL before redacting: redactPath
  // matches from the start, so a scheme and host would hide the prefix.
  let rest = value;
  let origin = '';
  const scheme = rest.match(ABSOLUTE_URL);
  if (scheme) {
    origin = scheme[0];
    rest = rest.slice(origin.length);
  }
  const query = rest.indexOf('?');
  const hash = rest.indexOf('#');
  let end = rest.length;
  if (query !== -1) end = Math.min(end, query);
  if (hash !== -1) end = Math.min(end, hash);
  return origin + redactPath(rest.slice(0, end));
}

function scrubText(value) {
  if (typeof value !== 'string') return value;
  // A path can arrive bare ("GET /j/SECRET") or inside an absolute URL
  // ("GET https://host/j/SECRET"); both carry the same credential, so
  // both go through the URL scrubber wherever they sit in the text.
  return value.replace(URL_IN_TEXT, (run) => {
    const stripped = run.replace(TRAILING_PUNCTUATION, '');
    const trailing = run.slice(stripped.length);
    // scrubUrl takes a bare path and an absolute URL alike: it redacts the
    // bearer segment and drops the query and fragment, which may hold a
    // credential on any path — not only a bearer one.
    return scrubUrl(stripped) + trailing;
  });
}

function scrubRequest(request) {
  if (!request || typeof request !== 'object') return request;
  const cleaned = { ...request };
  if (typeof cleaned.url === 'string') cleaned.url = scrubUrl(cleaned.url);
  for (const key of DROPPED_REQUEST_KEYS) delete cleaned[key];
  return cleaned;
}

function scrubSpan(span) {
  if (!span || typeof span !== 'object') return span;
  const cleaned = { ...span };
  if (typeof cleaned.description === 'string') {
    cleaned.description = scrubText(cleaned.description);
  }
  if (cleaned.data && typeof cleaned.data === 'object') {
    const data = { ...cleaned.data };
    for (const [key, value] of Object.entries(data)) {
      if (typeof value !== 'string') continue;
      if (URL_DATA_KEYS.has(key)) data[key] = scrubUrl(value);
      else if (value.startsWith('/')) data[key] = redactPath(value);
    }
    cleaned.data = data;
  }
  return cleaned;
}

function scrubBreadcrumb(crumb) {
  if (!crumb || typeof crumb !== 'object') return crumb;
  const cleaned = { ...crumb };
  if (typeof cleaned.message === 'string') {
    cleaned.message = scrubText(cleaned.message);
  }
  if (cleaned.data && typeof cleaned.data === 'object') {
    const data = { ...cleaned.data };
    for (const key of ['url', 'from', 'to']) {
      if (typeof data[key] === 'string') data[key] = scrubUrl(data[key]);
    }
    cleaned.data = data;
  }
  return cleaned;
}

function scrubExceptionValue(value) {
  if (!value || typeof value !== 'object') return value;
  const cleaned = { ...value };
  for (const key of ['value', 'type', 'module']) {
    if (typeof cleaned[key] === 'string') cleaned[key] = scrubText(cleaned[key]);
  }
  return cleaned;
}

export function scrubEvent(event) {
  if (!event || typeof event !== 'object') return event;
  const cleaned = { ...event };
  if (cleaned.request) cleaned.request = scrubRequest(cleaned.request);
  if (typeof cleaned.transaction === 'string') {
    cleaned.transaction = scrubText(cleaned.transaction);
  }
  if (typeof cleaned.message === 'string') {
    cleaned.message = scrubText(cleaned.message);
  }
  // An exception message can carry the failing URL, so the text fields
  // are scrubbed like any other free text, not only the request.
  if (cleaned.logentry && typeof cleaned.logentry === 'object') {
    const logentry = { ...cleaned.logentry };
    if (typeof logentry.message === 'string') {
      logentry.message = scrubText(logentry.message);
    }
    cleaned.logentry = logentry;
  }
  if (cleaned.exception && Array.isArray(cleaned.exception.values)) {
    cleaned.exception = {
      ...cleaned.exception,
      values: cleaned.exception.values.map(scrubExceptionValue),
    };
  }
  if (cleaned.user && typeof cleaned.user === 'object') {
    const user = { ...cleaned.user };
    delete user.ip_address;
    cleaned.user = user;
  }
  if (cleaned.breadcrumbs && Array.isArray(cleaned.breadcrumbs.values)) {
    cleaned.breadcrumbs = {
      ...cleaned.breadcrumbs,
      values: cleaned.breadcrumbs.values.map(scrubBreadcrumb),
    };
  }
  const tags = { ...(cleaned.tags || {}) };
  if (lastRequestId) tags.request_id = tags.request_id || lastRequestId;
  cleaned.tags = tags;
  return cleaned;
}

export function scrubTransaction(event) {
  const cleaned = scrubEvent(event);
  if (Array.isArray(cleaned.spans)) {
    cleaned.spans = cleaned.spans.map(scrubSpan);
  }
  return cleaned;
}

// Boot the SDK. No DSN means nothing loads and this is a no-op, which is
// what keeps a developer checkout free of network calls.
//
// The lazy chunk can fail to load on a flaky connection. That must not
// latch reporting off forever, so `started` is set only once the SDK is
// in hand — a failed import leaves it false and a later call retries. The
// failure is swallowed rather than rethrown: the caller carries on
// without a reporter, and there is no reporter to tell.
export async function initErrorReporting() {
  if (started || !DSN) return false;
  let Sentry;
  try {
    Sentry = await import('@sentry/browser');
  } catch {
    return false;
  }
  started = true;
  Sentry.init({
    dsn: DSN,
    environment: ENVIRONMENT,
    release: RELEASE,
    tracesSampleRate: Number.isFinite(TRACES_SAMPLE_RATE)
      ? TRACES_SAMPLE_RATE
      : 0.1,
    // tracesSampleRate only gates transactions that exist; this
    // integration is what creates them for page loads and fetch calls.
    integrations: [Sentry.browserTracingIntegration()],
    autoSessionTracking: false,
    sendDefaultPii: false,
    beforeSend: (event) => scrubEvent(event),
    beforeSendTransaction: (event) => scrubTransaction(event),
    beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
  });
  sentry = Sentry;
  return true;
}

// Report an error the app caught itself — a rejected boot, a failed
// mutation — with the failing request id attached when there is one. The
// id is passed explicitly when the caller has it (an API result carries
// its own), because the module-global is shared by concurrent requests;
// it falls back to the global for errors that have no request of their
// own.
export function reportError(error, context = {}, requestId = undefined) {
  if (!sentry) return;
  const id = requestId === undefined ? lastRequestId : requestId;
  sentry.withScope((scope) => {
    if (id) scope.setTag('request_id', id);
    // setContext takes a named object, so the scalar fields go in as one
    // "app" context rather than as a context per field — primitives do not
    // match the context schema and can be dropped on ingest.
    const fields = Object.fromEntries(
      Object.entries(context).filter(([, value]) => value !== undefined),
    );
    if (Object.keys(fields).length) scope.setContext('app', fields);
    sentry.captureException(error);
  });
}
