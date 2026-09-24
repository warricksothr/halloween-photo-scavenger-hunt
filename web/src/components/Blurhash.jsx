// A blurhash drawn on a canvas (ADR 0040).
//
// A canvas, not an <img> with a data: URL: the production CSP allows
// images from 'self' only, which is why the QR codes are drawn the same
// way. 32x32 pixels is plenty for a hash of 4x3 components; CSS stretches
// the canvas to the tile, and the browser's smoothing does the rest.
import { decode, isBlurhashValid } from 'blurhash';
import { useEffect, useRef } from 'preact/hooks';

const SIZE = 32;

export function Blurhash({ hash, class: className = '', label }) {
  const canvas = useRef(null);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext?.('2d');
    if (!ctx || !isBlurhashValid(hash).result) return;
    const pixels = decode(hash, SIZE, SIZE);
    const image = ctx.createImageData(SIZE, SIZE);
    image.data.set(pixels);
    ctx.putImageData(image, 0, 0);
  }, [hash]);

  return (
    <canvas
      ref={canvas}
      class={`blurhash ${className}`.trim()}
      width={SIZE}
      height={SIZE}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : 'true'}
    />
  );
}
