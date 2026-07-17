# Narratio Repository Cleanup Design

## Goal

Remove proven starter residue and stale documentation while leaving Narratio's pipeline, cover scraper, dependencies, screenshots, and runtime behavior unchanged.

## Scope

- Remove the unchanged Create Next App boilerplate at `frontend/README.md`.
- Remove the five unreferenced Create Next App SVG assets in `frontend/public/`.
- Remove the obsolete development-phase roadmap from `CLAUDE.md`.
- Remove the GitNexus section that points to six `.claude/skills/` files which do not exist in the repository.
- Correct README test instructions so they do not claim a test suite or test file that is absent.
- Add the standard MIT license with copyright attributed to `icon3333`.

## Explicitly Preserved

- All screenshots, including the large covers image.
- `uv.lock`, `frontend/package-lock.json`, environment examples, security guidance, and application code.
- The current Python-to-Node cover scraper and its dependency arrangement; consolidating it is a separate refactor.
- Pytest development dependencies, allowing a future test suite without another dependency change.

## Verification

- Confirm removed assets and missing GitNexus paths have no remaining references.
- Compile all Python modules.
- Run frontend lint and production build.
- Run the pipeline CLI help or import-safe smoke check without invoking external APIs.
- Review the final diff for non-behavioral changes only.

## Non-Goals

No scraper rewrite, dependency cleanup, screenshot compression, branch rename, repository metadata change, or application refactor.
