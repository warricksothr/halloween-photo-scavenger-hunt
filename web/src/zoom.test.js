// Resize-text configuration guard. Text zoom needs the viewport to allow
// scaling and the type scale to be relative, not pinned to pixels on the
// root element; both are cheap to assert without a browser. The behaviour
// at 200% — reflow and operability — is checked against the built app in
// e2e/resize-text.spec.js, which this does not replace.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

function read(relative) {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8');
}

describe('resize-text configuration', () => {
  it('lets the viewport scale', () => {
    const html = read('../index.html');
    const viewport = html.match(/<meta[^>]+name="viewport"[^>]*>/i)?.[0] ?? '';

    expect(viewport).not.toMatch(/user-scalable\s*=\s*no/i);
    expect(viewport).not.toMatch(/maximum-scale\s*=\s*1(\.0)?\b/i);
  });

  it('sets no fixed pixel font-size on the root', () => {
    const css = read('./themes/arkham/theme.css');

    expect(css).not.toMatch(/(?:^|[\s,{])(?:html|body|:root)\s*\{[^}]*font-size\s*:\s*\d+px/i);
  });
});
