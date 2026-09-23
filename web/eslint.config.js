// Frontend lint. Runs as the first half of `npm test`, so the same
// command the quality gate and CI already invoke fails on a lint error.
//
// Two environments: `src/` is browser code (JSX, browser globals, the
// hooks rules), while the configs and `e2e/` are Node code — the e2e
// specs also hold callbacks that Playwright evaluates in the page, so
// they get the browser globals too.
import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['dist/**', 'node_modules/**', '.playwright-results/**'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      // `process` is Vite's, read by the service-worker test for its cwd.
      globals: { ...globals.browser, process: 'readonly' },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    files: ['public/sw.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: { ...globals.browser, ...globals.serviceworker },
    },
  },
  {
    files: ['e2e/**/*.js', '*.config.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.node, ...globals.browser },
    },
  },
];
