// Which build of the web app this page is (ADR 0041).
//
// Vite inlines VITE_ERROR_RELEASE into the bundle at build time. It is the
// same value the error reporter tags events with (errors.js), and the
// container build already receives it from ARKHAM_RELEASE, so reading it
// here needs no new build argument on any host. A local build without it
// is "dev".
export const WEB_BUILD = import.meta.env.VITE_ERROR_RELEASE || 'dev';
