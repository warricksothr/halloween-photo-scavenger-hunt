# The GitHub Pages site

<https://warricksothr.github.io/halloween-photo-scavenger-hunt/> is served
from the `gh-pages` branch of the public GitHub mirror. That branch only
ever holds build output. Its source is on `main`:

| Published path | Source on `main` |
| --- | --- |
| `index.html` | `docs/site/index.html`, the project page |
| `screenshots/` | `docs/screenshots/`, the same captures the README shows |
| `mocks/` | `docs/impl/mocks/`, the design-phase mocks from 2026-08-14 |
| `.nojekyll` | written by the build, so Pages serves the files as they are |

This file is not published.

The project page takes its stylesheet from the mocks
(`mocks/assets/arkham-mock.css`), so it looks like the app without
depending on the app's build. Nothing is generated, and every published
byte is a file that was reviewed on `main`.

## Publish

Forgejo has no `gh-pages` branch and nothing publishes automatically.
Publish by hand after the change is merged to `main`, from a clone that
can push to the mirror:

```sh
M=git@github.com:warricksothr/halloween-photo-scavenger-hunt.git
git fetch origin main
git fetch "$M" refs/heads/gh-pages:refs/remotes/github/gh-pages

# Build from main, not from a working tree with local edits.
git worktree add --detach /tmp/pages-src origin/main
bash /tmp/pages-src/scripts/build-pages.sh /tmp/pages-out

# Replace the branch's contents with the build, as one new commit.
git worktree add --detach /tmp/pages github/gh-pages
git -C /tmp/pages rm -rq .
cp -R /tmp/pages-out/. /tmp/pages/
git -C /tmp/pages add -A
git -C /tmp/pages commit -m "Publish the Pages site from main $(git rev-parse --short origin/main)"
git -C /tmp/pages push "$M" HEAD:refs/heads/gh-pages

git worktree remove /tmp/pages
git worktree remove /tmp/pages-src
rm -rf /tmp/pages-out
```

The push is a fast-forward, a new commit on top of the branch, so the
site's history stays and nothing is force-pushed. Pages rebuilds within a
minute or two.

After a change to the README screenshots (`npm run screenshots`), the
project page or the mocks, publish again. Otherwise the site keeps the
last published copy.
