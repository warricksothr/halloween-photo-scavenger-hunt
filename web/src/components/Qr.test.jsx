import { render } from '@testing-library/preact';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Qr, qrPngBlob, qrSvgString } from './Qr';

const URL_TEXT = 'https://hunt.example/j/ABCDEF1234';

describe('QR rendering (ADR 0026)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('draws inline SVG sized by its prop, black on a white field', () => {
    const { container } = render(<Qr text={URL_TEXT} label="Join" size={200} />);
    const svg = container.querySelector('svg');
    expect(svg.getAttribute('width')).toBe('200');
    expect(svg.getAttribute('aria-label')).toBe('Join');
    const n = Number(svg.getAttribute('viewBox').split(' ')[2]);
    // Version 3 at ECC M (29 modules) plus the 2-module border each side.
    expect(n).toBeGreaterThanOrEqual(25);
    expect(svg.querySelector('rect').getAttribute('fill')).toBe('#ffffff');
    expect(svg.querySelector('path').getAttribute('fill')).toBe('#000000');
    expect(container.querySelector('img')).toBeNull();
  });

  it('writes the same matrix into the downloadable SVG', () => {
    const { container } = render(<Qr text={URL_TEXT} label="Join" />);
    const d = container.querySelector('path').getAttribute('d');
    expect(qrSvgString(URL_TEXT)).toContain(`d="${d}"`);
  });

  it('paints whole pixels per module onto the PNG canvas', async () => {
    const rects = [];
    const ctx = { fillRect: (...args) => rects.push(args), fillStyle: '' };
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx);
    let size;
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (cb) {
      size = this.width;
      cb(new Blob(['png'], { type: 'image/png' }));
    });

    const blob = await qrPngBlob(URL_TEXT, 1024);
    expect(blob.type).toBe('image/png');
    // The background, then one square per dark module, all the same size.
    const [, ...modules] = rects;
    const scale = modules[0][2];
    expect(Number.isInteger(scale)).toBe(true);
    expect(size % scale).toBe(0);
    expect(size).toBeLessThanOrEqual(1024);
    expect(modules.every((r) => r[2] === scale && r[3] === scale)).toBe(true);
  });
});
