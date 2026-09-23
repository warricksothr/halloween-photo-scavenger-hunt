import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// @sentry/browser is only imported when a DSN is set; the mock stands in
// for the real SDK so nothing reaches the network.
const sentryMock = {
  init: vi.fn(),
  withScope: vi.fn(),
  captureException: vi.fn(),
  browserTracingIntegration: vi.fn(() => ({ name: 'BrowserTracing' })),
};
vi.mock('@sentry/browser', () => sentryMock);

async function loadErrors({ dsn } = {}) {
  vi.resetModules();
  if (dsn) vi.stubEnv('VITE_ERROR_DSN', dsn);
  else vi.stubEnv('VITE_ERROR_DSN', '');
  return import('./errors');
}

describe('error reporting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sentryMock.withScope.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('stays inert without a DSN', async () => {
    const errors = await loadErrors();

    await expect(errors.initErrorReporting()).resolves.toBe(false);
    expect(sentryMock.init).not.toHaveBeenCalled();
  });

  it('initializes the SDK, with sessions off, when a DSN is set', async () => {
    const errors = await loadErrors({ dsn: 'https://key@glitchtip.example/1' });

    await expect(errors.initErrorReporting()).resolves.toBe(true);
    expect(sentryMock.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: 'https://key@glitchtip.example/1',
        autoSessionTracking: false,
        sendDefaultPii: false,
      }),
    );
  });

  it('installs browser tracing so transactions are created', async () => {
    const errors = await loadErrors({ dsn: 'https://key@glitchtip.example/1' });

    await errors.initErrorReporting();

    expect(sentryMock.browserTracingIntegration).toHaveBeenCalled();
    const config = sentryMock.init.mock.calls[0][0];
    expect(config.integrations).toContainEqual({ name: 'BrowserTracing' });
  });

  it('retries a failed SDK import instead of latching reporting off', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_ERROR_DSN', 'https://key@glitchtip.example/1');
    let attempts = 0;
    vi.doMock('@sentry/browser', () => {
      attempts += 1;
      if (attempts === 1) throw new Error('chunk failed to load');
      return sentryMock;
    });
    const errors = await import('./errors');

    await expect(errors.initErrorReporting()).resolves.toBe(false);
    expect(sentryMock.init).not.toHaveBeenCalled();

    await expect(errors.initErrorReporting()).resolves.toBe(true);
    expect(sentryMock.init).toHaveBeenCalledTimes(1);
    vi.doMock('@sentry/browser', () => sentryMock);
  });

  it('reports under an explicit request id over the shared global', async () => {
    const errors = await loadErrors({ dsn: 'https://key@glitchtip.example/1' });
    await errors.initErrorReporting();
    errors.recordRequestId('req-global');

    const scope = { setTag: vi.fn(), setContext: vi.fn() };
    sentryMock.withScope.mockImplementation((fn) => fn(scope));

    errors.reportError(new Error('boom'), { where: 'join' }, 'req-own');

    expect(scope.setTag).toHaveBeenCalledWith('request_id', 'req-own');
  });

  it('records the last request id and attaches it as a tag', async () => {
    const errors = await loadErrors();
    errors.recordRequestId('req-123');

    const event = errors.scrubEvent({ tags: {} });

    expect(event.tags.request_id).toBe('req-123');
  });

  it('scrubs a credential path out of a request URL', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({
      request: { url: 'https://hunt.example/api/join/SECRET?t=1' },
    });

    expect(event.request.url).toBe('https://hunt.example/api/join/<redacted>');
  });

  it('drops headers, cookies and query string from the request', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({
      request: {
        url: 'https://hunt.example/api/state',
        headers: { Cookie: 'session=leak' },
        cookies: 'session=leak',
        query_string: 'token=leak',
        env: { SECRET: 'leak' },
        data: 'leak',
      },
    });

    expect(event.request.headers).toBeUndefined();
    expect(event.request.cookies).toBeUndefined();
    expect(event.request.query_string).toBeUndefined();
    expect(event.request.env).toBeUndefined();
    expect(event.request.data).toBeUndefined();
  });

  it('redacts the credential in a transaction name', async () => {
    const errors = await loadErrors();

    const event = errors.scrubTransaction({
      transaction: 'GET /api/team/invites/SECRET',
    });

    expect(event.transaction).toBe('GET /api/team/invites/<redacted>');
  });

  it('redacts a credential inside an absolute URL in a transaction name', async () => {
    const errors = await loadErrors();

    const event = errors.scrubTransaction({
      transaction: 'GET https://hunt.example/api/join/SECRET',
    });

    expect(event.transaction).toBe(
      'GET https://hunt.example/api/join/<redacted>',
    );
  });

  it('reaches a path wrapped in prose, quoting, or a newline', async () => {
    const errors = await loadErrors();

    expect(
      errors.scrubEvent({ message: "request to '/api/join/SECRET' failed" })
        .message,
    ).toBe("request to '/api/join/<redacted>' failed");
    expect(errors.scrubEvent({ message: 'url=/api/join/SECRET,' }).message).toBe(
      'url=/api/join/<redacted>,',
    );
    expect(
      errors.scrubEvent({ message: 'GET\n/api/join/SECRET\nfailed' }).message,
    ).toBe('GET\n/api/join/<redacted>\nfailed');
  });

  it('redacts span descriptions and URL-shaped span data', async () => {
    const errors = await loadErrors();

    const event = errors.scrubTransaction({
      spans: [
        {
          description: 'GET /m/SECRET',
          data: { url: 'https://hunt.example/j/SECRET' },
        },
      ],
    });

    expect(event.spans[0].description).toBe('GET /m/<redacted>');
    expect(event.spans[0].data.url).toBe('https://hunt.example/j/<redacted>');
  });

  it('redacts the credential in breadcrumb messages and data', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({
      breadcrumbs: {
        values: [
          {
            message: 'navigated to /t/SECRET',
            data: { from: '/j/SECRET' },
          },
        ],
      },
    });

    expect(event.breadcrumbs.values[0].message).toBe('navigated to /t/<redacted>');
    expect(event.breadcrumbs.values[0].data.from).toBe('/j/<redacted>');
  });

  it('redacts a credential inside an absolute URL in a breadcrumb message', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({
      breadcrumbs: {
        values: [{ message: 'GET https://hunt.example/j/SECRET' }],
      },
    });

    expect(event.breadcrumbs.values[0].message).toBe(
      'GET https://hunt.example/j/<redacted>',
    );
  });

  it('redacts a credential in a top-level event message', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({ message: 'GET /api/join/SECRET failed' });

    expect(event.message).toBe('GET /api/join/<redacted> failed');
  });

  it('redacts a credential inside an exception message', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({
      exception: {
        values: [
          { type: 'TypeError', value: 'GET /api/join/SECRET failed' },
        ],
      },
      logentry: { message: 'GET https://hunt.example/t/SECRET failed' },
    });

    expect(event.exception.values[0].value).toBe('GET /api/join/<redacted> failed');
    expect(event.logentry.message).toBe(
      'GET https://hunt.example/t/<redacted> failed',
    );
  });

  it('drops the user IP from an event', async () => {
    const errors = await loadErrors();

    const event = errors.scrubEvent({ user: { ip_address: '1.2.3.4' } });

    expect(event.user.ip_address).toBeUndefined();
  });

  it('reports a caught error with the request id tagged', async () => {
    const errors = await loadErrors({ dsn: 'https://key@glitchtip.example/1' });
    await errors.initErrorReporting();
    errors.recordRequestId('req-123');

    const scope = { setTag: vi.fn(), setContext: vi.fn() };
    sentryMock.withScope.mockImplementation((fn) => fn(scope));

    errors.reportError(new Error('boom'), { op: 'boot' });

    expect(scope.setTag).toHaveBeenCalledWith('request_id', 'req-123');
    expect(scope.setContext).toHaveBeenCalledWith('op', 'boot');
    expect(sentryMock.captureException).toHaveBeenCalled();
  });
});
