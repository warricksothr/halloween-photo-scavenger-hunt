import { render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { BuildTag } from './BuildTag';

describe('build tag (ADR 0041)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('names the build it is given', () => {
    render(<BuildTag build="37486df" />);
    expect(screen.getByText('Build 37486df')).toBeTruthy();
  });

  // version.js reads the variable once, at import, so each case stubs it
  // and imports a fresh copy of the module.
  it('reads the release baked into the bundle', async () => {
    vi.stubEnv('VITE_ERROR_RELEASE', 'abc1234');
    vi.resetModules();
    const { BuildTag: Fresh } = await import('./BuildTag');
    render(<Fresh />);
    expect(screen.getByText('Build abc1234')).toBeTruthy();
  });

  it('says "dev" when no release was baked in', async () => {
    vi.stubEnv('VITE_ERROR_RELEASE', '');
    vi.resetModules();
    const { BuildTag: Fresh } = await import('./BuildTag');
    render(<Fresh />);
    expect(screen.getByText('Build dev')).toBeTruthy();
  });
});
