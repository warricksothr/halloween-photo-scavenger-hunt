// In-game navigation backed by the browser's history (ADR 0036).
//
// The game is one document with no router, so for a long time a screen
// change left no trace in history. The iOS edge swipe and the browser's
// Back then left the app, and the installed app, which has no browser
// chrome, had no Back at all. Each screen change now pushes a history
// entry that carries the screen, so Back and the swipe move between
// screens, and the in-app Back buttons call history.back() so they agree
// with the swipe.
//
// The URL never changes: the entries live in history.state, under one
// key, beside whatever else is there. A reload restores the screen from
// the current entry. Join links (/j/<code>) and the store's own
// replaceState calls are untouched.
import { useEffect, useState } from 'preact/hooks';

const KEY = 'arkhamNav';

// A screen: the tab, the riddle open on the riddles tab, and the riddle
// the drawer should return to when it was opened from one. depth counts
// entries this game pushed, so Back knows whether history.back() stays
// inside the game. event keeps another game's entries from applying.
export function home(event) {
  return { event, tab: 'riddles', riddle: null, returnTo: null, depth: 0 };
}

function current(event) {
  const nav = window.history.state?.[KEY];
  return nav && nav.event === event ? nav : null;
}

function write(method, nav) {
  window.history[method]({ ...(window.history.state ?? {}), [KEY]: nav }, '');
}

// Where Back goes when there is no pushed entry to return to, as after a
// reload: the drawer returns to the riddle that opened it, a riddle to the
// board.
function parent(nav) {
  if (nav.tab === 'drawer' && nav.returnTo) {
    return { ...nav, tab: 'riddles', riddle: nav.returnTo, returnTo: null };
  }
  return home(nav.event);
}

export function useGameNav(event) {
  const [nav, setNav] = useState(() => current(event) ?? home(event));
  // A photo to select when the riddle it was taken for opens again.
  const [selectOnReturn, setSelectOnReturn] = useState(null);

  useEffect(() => {
    // Mark the entry the game started on, so Back to it restores the
    // board instead of finding an entry with no screen. With no entry for
    // this game, the first screen is the board (useState's default).
    if (!current(event)) write('replaceState', home(event));
    function onPop(e) {
      const next = e.state?.[KEY];
      // An entry from before this game, or from another game, is not a
      // screen here; the board is the safe place to land.
      setNav(next && next.event === event ? next : home(event));
    }
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [event]);

  function go(target) {
    const next = { ...home(event), ...target, depth: nav.depth + 1 };
    if (next.tab === nav.tab && next.riddle === nav.riddle && next.returnTo === nav.returnTo) {
      return;
    }
    setSelectOnReturn(null);
    write('pushState', next);
    setNav(next);
  }

  function back() {
    if (nav.depth > 0) {
      window.history.back();
      return;
    }
    const up = parent(nav);
    write('replaceState', up);
    setNav(up);
  }

  // Replace this screen without a new entry: for a riddle that vanished
  // from the snapshot, where Back would only lead to it again.
  function leave() {
    const up = { ...home(event), depth: nav.depth };
    write('replaceState', up);
    setNav(up);
  }

  // After a photo taken for a riddle is saved: back to that riddle, with
  // the photo selected.
  function returnWith(evidenceId) {
    const riddle = nav.returnTo;
    back();
    setSelectOnReturn({ riddle, evidenceId });
  }

  const selected =
    selectOnReturn && selectOnReturn.riddle === nav.riddle ? selectOnReturn.evidenceId : null;

  return { nav, go, back, leave, returnWith, selected };
}
