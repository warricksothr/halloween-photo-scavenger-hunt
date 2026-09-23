// Shared setup for the browser specs.
//
// The API requires a signed CSRF token on every mutation (app/csrf.py): a
// safe GET plants the `arkham_csrf` cookie, and the value rides the
// `X-CSRF-Token` header. A Playwright `APIRequestContext` has no cookie jar
// of its own until the first response, so every spec that drives the admin
// API needs the same dance. Keep it here rather than in each spec.
import { expect } from '@playwright/test';

export const ADMIN_USERNAME = 'browser-test-admin';
export const ADMIN_PASSWORD = 'browser-test-only';
export const BASE_URL = 'http://127.0.0.1:4173';

export async function adminApi(playwright) {
  const api = await playwright.request.newContext({ baseURL: BASE_URL });

  await api.get('/api/health');
  const { cookies } = await api.storageState();
  const csrf = cookies.find((cookie) => cookie.name === 'arkham_csrf')?.value;
  expect(csrf, 'a safe GET should plant the CSRF cookie').toBeTruthy();
  const headers = { 'X-CSRF-Token': csrf };

  return {
    headers,
    get: (path, options = {}) => api.get(path, options),
    post: (path, options = {}) =>
      api.post(path, { ...options, headers: { ...headers, ...options.headers } }),
    dispose: () => api.dispose(),
  };
}

export async function loginAdmin(admin) {
  const login = await admin.post('/api/admin/login', {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
}
