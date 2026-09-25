import { render, screen } from '@testing-library/preact';
import { describe, expect, it } from 'vitest';

import { WEB_BUILD } from '../version';
import { BuildTag } from './BuildTag';

describe('build tag (ADR 0041)', () => {
  it('names the build it is given', () => {
    render(<BuildTag build="37486df" />);
    expect(screen.getByText('Build 37486df')).toBeTruthy();
  });

  it('defaults to the bundle build, "dev" when none was baked in', () => {
    render(<BuildTag />);
    expect(screen.getByText(`Build ${WEB_BUILD}`)).toBeTruthy();
    expect(WEB_BUILD).toBe(import.meta.env.VITE_ERROR_RELEASE || 'dev');
  });
});
