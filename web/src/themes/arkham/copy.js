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
    join: {
      headline: 'Gotham Needs You',
      subtext: 'Enter your codename to join the hunt.',
      nameLabel: 'Codename',
      deviceLabel: 'Device label (optional)',
      submit: 'Join the Hunt',
    },
    lobby: {
      headline: 'Stand By',
      subtext: 'The round has not opened yet. The Batcomputer will light up when it does.',
    },
    riddles: {
      headline: 'Riddle Board',
      empty: 'No riddles on the board yet.',
    },
  },

  tiles: {
    unsolvedGlyph: '?',
  },
};
