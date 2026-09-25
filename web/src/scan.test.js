import { describe, expect, it } from 'vitest';

import { scanTarget, scanWidths } from './scan';

const ORIGIN = 'https://scavenger.example';

describe('scanTarget (ADR 0043)', () => {
  it('opens this site\'s join, invite and moderator links by path', () => {
    expect(scanTarget(`${ORIGIN}/j/ABCD234567`, ORIGIN)).toBe('/j/ABCD234567');
    expect(scanTarget(`${ORIGIN}/t/XYZW987654/`, ORIGIN)).toBe('/t/XYZW987654');
    expect(scanTarget(`  ${ORIGIN}/m/MODE234567\n`, ORIGIN)).toBe('/m/MODE234567');
  });

  it('refuses a hunt link carrying a query or fragment, rather than trimming it', () => {
    expect(scanTarget(`${ORIGIN}/j/ABCD234567?next=https://evil.example`, ORIGIN)).toBeNull();
    expect(scanTarget(`${ORIGIN}/j/ABCD234567#x`, ORIGIN)).toBeNull();
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

describe('scanWidths', () => {
  it('scans a phone photo at 1024, 1600 and 640 on the long edge', () => {
    expect(scanWidths(4032, 3024)).toEqual([
      { width: 1024, height: 768 },
      { width: 1600, height: 1200 },
      { width: 640, height: 480 },
    ]);
  });

  it('still tries 640 when the photo is smaller than the larger passes', () => {
    expect(scanWidths(1200, 900)).toEqual([
      { width: 1024, height: 768 },
      { width: 1200, height: 900 },
      { width: 640, height: 480 },
    ]);
    expect(scanWidths(800, 600)).toEqual([
      { width: 800, height: 600 },
      { width: 640, height: 480 },
    ]);
    expect(scanWidths(500, 500)).toEqual([{ width: 500, height: 500 }]);
  });
});
