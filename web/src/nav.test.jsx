import { act, render } from '@testing-library/preact';
import { beforeEach, describe, expect, it } from 'vitest';

import { useGameNav } from './nav';

// Drives the hook through a probe component and hands back its latest
// return value, the way GameShell uses it.
function mount(event = 'ev-1') {
  const probe = {};
  function Probe() {
    Object.assign(probe, useGameNav(event));
    return null;
  }
  const view = render(<Probe />);
  return { probe, view };
}

// jsdom's history.back() is asynchronous and fires popstate, as a browser's
// does; this waits for it.
async function goBack() {
  await act(async () => {
    const popped = new Promise((resolve) => window.addEventListener('popstate', resolve, { once: true }));
    window.history.back();
    await popped;
  });
}

describe('game navigation (ADR 0036)', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('starts on the board and marks the starting entry', () => {
    const { probe } = mount();
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: null, depth: 0 });
    expect(window.history.state.arkhamNav.tab).toBe('riddles');
  });

  it('pushes an entry per screen, and Back returns to the one before', async () => {
    const { probe } = mount();
    const start = window.history.length;
    act(() => probe.go({ tab: 'riddles', riddle: 'r-2' }));
    expect(probe.nav).toMatchObject({ riddle: 'r-2', depth: 1 });
    act(() => probe.go({ tab: 'team' }));
    expect(window.history.length).toBe(start + 2);

    await goBack();
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: 'r-2' });
    await goBack();
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: null });
  });

  it('does not stack an entry for the screen already showing', () => {
    const { probe } = mount();
    const start = window.history.length;
    act(() => probe.go({ tab: 'riddles' }));
    expect(window.history.length).toBe(start);
  });

  it('returns from the drawer to its riddle with the new photo selected', async () => {
    const { probe } = mount();
    act(() => probe.go({ tab: 'riddles', riddle: 'r-3' }));
    act(() => probe.go({ tab: 'drawer', returnTo: 'r-3' }));
    expect(probe.nav).toMatchObject({ tab: 'drawer', returnTo: 'r-3' });

    await act(async () => {
      const popped = new Promise((resolve) => window.addEventListener('popstate', resolve, { once: true }));
      probe.returnWith('ev-new');
      await popped;
    });
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: 'r-3' });
    expect(probe.selected).toBe('ev-new');

    // Going elsewhere clears it, so a later visit starts unselected.
    act(() => probe.go({ tab: 'team' }));
    expect(probe.selected).toBeNull();
  });

  it('restores the screen from the entry after a reload', () => {
    const first = mount();
    act(() => first.probe.go({ tab: 'drawer', returnTo: 'r-1' }));
    first.view.unmount();

    const { probe } = mount();
    expect(probe.nav).toMatchObject({ tab: 'drawer', returnTo: 'r-1' });
  });

  it('after a reload, Back retraces the same entries the browser would', async () => {
    const first = mount();
    act(() => first.probe.go({ tab: 'riddles', riddle: 'r-1' }));
    act(() => first.probe.go({ tab: 'standings' }));
    first.view.unmount();

    const { probe } = mount();
    expect(probe.nav).toMatchObject({ tab: 'standings' });
    await act(async () => {
      const popped = new Promise((resolve) => window.addEventListener('popstate', resolve, { once: true }));
      probe.back();
      await popped;
    });
    // The swipe lands here too: the entry before Standings.
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: 'r-1' });
  });

  it('with nothing pushed, Back goes up a level instead of leaving', () => {
    window.history.replaceState(
      { arkhamNav: { event: 'ev-1', tab: 'drawer', riddle: null, returnTo: 'r-1', depth: 0 } },
      '',
    );
    const { probe } = mount();
    act(() => probe.back());
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: 'r-1' });
    act(() => probe.back());
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: null });
  });

  it("ignores another game's entries", async () => {
    window.history.replaceState(
      { arkhamNav: { event: 'other', tab: 'team', riddle: null, returnTo: null, depth: 0 } },
      '',
    );
    const { probe } = mount('ev-1');
    expect(probe.nav).toMatchObject({ event: 'ev-1', tab: 'riddles' });
  });

  it('leaves a vanished riddle without adding an entry', () => {
    const { probe } = mount();
    act(() => probe.go({ tab: 'riddles', riddle: 'gone' }));
    const length = window.history.length;
    act(() => probe.leave());
    expect(probe.nav).toMatchObject({ tab: 'riddles', riddle: null });
    expect(window.history.length).toBe(length);
  });
});
