// Arkham theme pack — copy config.
//
// Every themed string the app shows lives here, keyed by purpose. The
// neutral core (screens/components) asks for copy by key; a new theme
// pack supplies the same keys in its own voice. Copy source:
// docs/reference/THEME-NOTES.md "Verdict copy bank".
//
// Conduct strings (strikes) are deliberately absent: conduct surfaces
// are un-themed by rule (design.md) and use plain copy hardcoded at the
// call site, so nothing here can accidentally decorate them.

export default {
  name: 'arkham',

  verdicts: {
    // submission.status → banner copy
    pending: {
      headline: 'SCANNING…',
      subtext: 'Cross-referencing with Batcomputer database…',
    },
    verified: {
      headline: 'RIDDLE SOLVED.',
      subtext: 'The Riddler underestimates you, detective.',
    },
    obscured: {
      headline: 'SUBJECT OBSCURED.',
      subtext: 'Detective vision cannot resolve the subject — adjust your angle.',
    },
    not_found: {
      headline: 'SUBJECT NOT FOUND.',
      subtext: 'The Batcomputer finds no match. Wrong subject, detective.',
    },
    too_small: {
      headline: 'SUBJECT TOO SMALL.',
      subtext: 'Move closer, detective.',
    },
    misaligned: {
      headline: 'MISALIGNED.',
      subtext: 'Solution partially detected — reframe the subject and try again.',
    },
    expired: {
      headline: 'INTEL EXPIRED.',
      subtext: 'The round ended before this one was reviewed.',
    },
    // inappropriate is a conduct verdict: un-themed by rule, so it is
    // NOT here — the strike flow (increment 8) renders plain copy.
  },

  screens: {
    // Shown while the store boots, before any event theme is known. The
    // loader serves it from the default pack (theme.js: defaultCopy).
    boot: {
      loading: 'Waking the Batcomputer…',
    },
    join: {
      headline: 'Gotham Needs You',
      subtext: 'Enter your codename to join the hunt.',
      nameLabel: 'Codename',
      deviceLabel: 'Device label (optional)',
      codeLabel: 'Join code',
      codePlaceholder: 'from the QR at the door',
      devicePlaceholder: "Sam's phone",
      submit: 'Join the Hunt',
      // Rejoin (ADR 0031): games this device already joined.
      resumeHeading: 'Open Cases',
      resumeAs: (name) => `Return as ${name}`,
      resumeOr: 'Or join another hunt:',
      // The install suggestion (TKT-01M390Y0VQ). On an iPhone the app keeps
      // its own sign-in apart from Safari, so it asks to install first and
      // names the code to join with in the app.
      install: {
        headline: 'Install the Batcomputer',
        iosSteps: 'Tap Share (the square with the arrow), then Add to Home Screen.',
        iosThen: (code) =>
          code
            ? `Then open Arkham Hunt from your home screen and join there with code ${code}. The app keeps its own sign-in, apart from Safari.`
            : 'Then open Arkham Hunt from your home screen and join there. The app keeps its own sign-in, apart from Safari.',
        promptBody: 'Add it to your home screen for a full-screen view.',
        install: 'Install',
        dismiss: 'Not now',
      },
    },
    // The header's Switch Case control (ADR 0033): back to Open Cases,
    // keeping this hunt listed there.
    header: {
      switchGame: 'Switch Case',
    },
    lobby: {
      headline: 'Stand By',
      subtext: 'The round has not opened yet. The Batcomputer will light up when it does.',
    },
    riddles: {
      headline: 'Riddle Board',
      empty: 'No riddles on the board yet.',
      // A tile's only visible content is a glyph, so its accessible name
      // has to carry the riddle and its state for screen readers.
      tile: (state, text) =>
        state === 'verified'
          ? `Riddle solved: ${text}`
          : state === 'pending'
            ? `Riddle scanning: ${text}`
            : `Open riddle: ${text}`,
    },
    detail: {
      back: '← Back to the board',
      pickEvidence: 'Submit evidence',
      submit: 'Submit to the Batcomputer',
      submitting: 'Transmitting…',
      loading: 'Opening the drawer…',
      emptyDrawer: 'The drawer is empty — take a photo first',
      // The evidence picker's thumbnails carry no text, so each option
      // is named by position.
      evidenceOption: (position) => `Evidence photo ${position}`,
      // Shown when the double-tap race 409s: the submission the player
      // wanted already exists, so this is reassurance, not an error.
      alreadyScanning: 'Already scanning this one — no need to resubmit.',
      // One photo serves one riddle (ADR 0035). A photo in use stays in the
      // picker, greyed out and labelled with the riddle holding it.
      inUsePending: (n) => `Scanning · Riddle ${n}`,
      inUseSolved: (n) => `Solved · Riddle ${n}`,
      // Always offered under the picker; the drawer returns here with the
      // new photo selected.
      takeNew: 'Take a new photo',
      rejectedOn: (n) => `rejected on Riddle ${n}`,
      photoTaken: (n) => `That photo is already on Riddle ${n}. Pick another or take a new one.`,
      // The hint ladder. Nothing shows until the player asks, and each
      // press costs them one more level of the reveal.
      needNudge: 'Need a nudge?',
      noMoreHints: 'That is every hint for this one.',
    },
    drawer: {
      headline: 'Evidence Drawer',
      capture: 'Take a Photo',
      addLabel: 'Add a photo',
      photoAlt: 'Your evidence photo',
      uploading: 'Uploading…',
      loading: 'Opening the drawer…',
      empty: 'No evidence yet. Take a photo of something suspicious.',
      // Opened from a riddle: a way back, and a promise of where the photo
      // goes.
      backToRiddle: (n) => `← Back to Riddle ${n}`,
      // Each photo's state on its tile (ADR 0040). A scanning photo and a
      // removed one show only as a blur. The removed label is neutral: the
      // whole team sees it, and conduct matters are not announced to them.
      scanning: (n) => `Scanning · Riddle ${n}`,
      scanningAlt: 'Your photo, blurred while it is scanned',
      solved: (n) => `Solved · Riddle ${n}`,
      rejected: (n) => `Rejected · Riddle ${n}`,
      removed: 'Photo removed',
      removedAlt: 'A removed photo, shown blurred',
      forRiddle: (n) => `Shooting for Riddle ${n}. The photo will be ready to submit there.`,
    },
    standings: {
      headline: 'Standings',
      // final-reveal mid-round (snapshot.leaderboard is null)
      sealed: 'Standings are sealed — the host reveals them when the round closes.',
      empty: 'No operatives on the board yet.',
      loading: "Compiling the night's intel…",
      error: 'The final report could not be retrieved.',
      retry: 'Try again',
      // Closed, but no team scored — the celebration line needs a fallback.
      noWinner: 'Final standings are in.',
      caseClosed: 'Case Closed',
      caseClosedSubtext: (winner, score, total) =>
        `${winner} solved Gotham — ${score} of ${total} riddles. Final standings are in.`,
      recapHeadline: "The Night's Intel Trail",
      you: '(you)',
    },
    team: {
      headline: 'Strike Team',
      loading: 'Assembling the roster…',
      namePlaceholder: 'Name your team',
      operatives: 'operatives',
      editName: 'Edit',
      saveName: 'Save',
      cancel: 'Cancel',
      roster: 'Roster',
      you: '(you)',
      recruit: 'Recruit an Operative',
      createInvite: 'Create invite link',
      newCode: 'New code',
      revoke: 'Revoke',
      singleUse: 'Single-use',
      expiresIn: 'expires in',
      teamFull: 'The team is at full strength.',
      inviteNote:
        'Share the link with your teammate — it works once, for ten minutes.',
      // Sign out on a shared phone: unlike Switch Case, it forgets the hunt.
      signOutHeading: 'Hand Off This Phone',
      signOutNote:
        'Passing this phone to someone else? Sign out so it forgets this hunt.',
      signOut: 'Sign out of this phone',
      signOutConfirm:
        'This phone will forget this hunt: it will not be listed under Open Cases here again, and your codename cannot be picked up from this device.',
      signOutYes: 'Sign out',
      signOutNo: 'Keep playing',
      // Roster last-seen, in the pack's voice. `mins` is null when the
      // member has never been seen; the component owns the clock math.
      lastSeen: (mins) => {
        if (mins === null) return 'never seen';
        if (mins < 1) return 'active now';
        if (mins < 60) return `${mins} min ago`;
        return `${Math.floor(mins / 60)} h ${mins % 60} min ago`;
      },
    },
    teamJoin: {
      // The /t/<token> landing: an invite, not a join code. Themed like
      // join (it is game onboarding, not a conduct surface).
      headline: 'You Have Been Recruited',
      loading: 'Checking the invite…',
      unavailable: 'Invite Unavailable',
      teamLine: (teamName, eventName) =>
        teamName
          ? `${teamName} wants you on their team — ${eventName}.`
          : `A strike team wants you — ${eventName}.`,
      nameLabel: 'Codename',
      join: 'Join the Team',
      expired: 'That invite link is expired or already used. Ask for a fresh one.',
      // Switch warning (design.md invite edge case; mocks/team.html):
      // an existing player with evidence gets the honest version.
      switchHeadline: 'Changing Teams?',
      switchBody:
        'Your evidence and submission history stay with your current team. This cannot be undone.',
      stay: 'Stay',
      switchConfirm: 'Switch team',
      full: 'That team is full.',
    },
  },

  tabs: {
    riddles: 'Riddles',
    drawer: 'Drawer',
    team: 'Team',
    standings: 'Standings',
  },

  // Recap timeline (increment 9, ADR 0005): the server ships facts
  // (kind + team + riddle number), the theme pack renders the fiction.
  // These are game-facing celebration lines, so they ARE themed — the
  // un-themed-by-rule list is conduct surfaces only.
  recap: {
    opened: (n) =>
      `The host opened the hunt — ${n} operative${n === 1 ? '' : 's'} linked in`,
    closed: (n) =>
      n > 0
        ? `The window closed. Intel expired on ${n} pending scan${n === 1 ? '' : 's'}.`
        : 'The window closed — every scan reviewed.',
    reopened: () => 'The host reopened the hunt — back in play',
    firstSolve: (e) =>
      `${e.team} drew first blood — Riddle #${e.riddle_sort} verified`,
    solve: (e) =>
      `${e.team} verified Riddle #${e.riddle_sort}`,
    leadChange: (e) =>
      `${e.team} took the lead (${e.score} solved)`,
    massSolve: (e) =>
      `Riddle #${e.riddle_sort} fell to every team — no match for Gotham`,
  },

  tiles: {
    unsolvedGlyph: '?',
  },
};
