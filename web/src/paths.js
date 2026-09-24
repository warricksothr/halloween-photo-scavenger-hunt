// Path matchers shared by the shell (main.jsx) and the store. The store
// needs them too: on a moderator path it probes the moderator session
// first, so a browser that also holds a player session still reaches the
// console (TKT-01M394KVSC6GCC1EDW4NSXZRW3).

// The moderator surfaces (S9CW): the link (/m/<code>), the bare code
// form (/mod, where the OIDC callback lands a signed-in moderator), and
// any deeper path. Matched by segment so a player path like /modify is
// not swallowed.
export function isModPath(pathname) {
  return (
    pathname === '/m' ||
    pathname.startsWith('/m/') ||
    pathname === '/mod' ||
    pathname.startsWith('/mod/')
  );
}

// The code a /m/<code> link carries, or null.
export function modLinkCode(pathname) {
  const match = pathname.match(/^\/m\/([A-Za-z0-9]+)/);
  return match ? match[1] : null;
}
