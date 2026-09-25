import { describe, expect, it } from 'vitest';

import { scanTarget } from './scan';

const ORIGIN = 'https://scavenger.example';

describe('scanTarget (ADR 0043)', () => {
  it('opens this site\'s join, invite and moderator links by path', () => {
    expect(scanTarget(`${ORIGIN}/j/ABCD234567`, ORIGIN)).toBe('/j/ABCD234567');
    expect(scanTarget(`${ORIGIN}/t/XYZW987654/`, ORIGIN)).toBe('/t/XYZW987654');
    expect(scanTarget(`  ${ORIGIN}/m/MODE234567\n`, ORIGIN)).toBe('/m/MODE234567');
  });

  it('keeps only the path, never a query or fragment', () => {
    expect(scanTarget(`${ORIGIN}/j/ABCD234567?next=https://evil.example#x`, ORIGIN))
      .toBe('/j/ABCD234567');
  });

  it('refuses another origin, even with a hunt-shaped path', () => {
    expect(scanTarget('https://evil.example/j/ABCD234567', ORIGIN)).toBeNull();
    expect(scanTarget('http://scavenger.example/j/ABCD234567', ORIGIN)).toBeNull();
  });

  it('refuses other paths and non-links', () => {
    expect(scanTarget(`${ORIGIN}/admin`, ORIGIN)).toBeNull();
    expect(scanTarget(`${ORIGIN}/j/ABCD234567/extra`, ORIGIN)).toBeNull();
    expect(scanTarget(`${ORIGIN}/j/../admin`, ORIGIN)).toBeNull();
    expect(scanTarget(`${ORIGIN}/x/ABCD234567`, ORIGIN)).toBeNull();
    expect(scanTarget('ABCD234567', ORIGIN)).toBeNull();
    expect(scanTarget('javascript:alert(1)', ORIGIN)).toBeNull();
    expect(scanTarget('', ORIGIN)).toBeNull();
  });
});
