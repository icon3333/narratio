# Narratio Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove unreferenced Next.js residue, repair stale documentation, and license Narratio under MIT without changing runtime behavior.

**Architecture:** Keep the pipeline, API, frontend, scraper, dependencies, lockfiles, and screenshots intact. Limit edits to unused assets, boilerplate, contributor-facing documentation, and the root license.

**Tech Stack:** Markdown, MIT license text, Python 3.12, Next.js/ESLint

## Global Constraints

- Do not modify Python or TypeScript application source.
- Preserve screenshots, lockfiles, security guidance, environment examples, dependencies, and scraper files.
- Attribute the MIT copyright to `icon3333` for 2026.
- Do not publish, rename branches, or change GitHub settings.

---

### Task 1: Remove starter residue and correct repository guidance

**Files:**
- Delete: `frontend/README.md`
- Delete: `frontend/public/file.svg`
- Delete: `frontend/public/globe.svg`
- Delete: `frontend/public/next.svg`
- Delete: `frontend/public/vercel.svg`
- Delete: `frontend/public/window.svg`
- Modify: `CLAUDE.md:99-end`
- Modify: `README.md:Development`
- Create: `LICENSE`

**Interfaces:**
- Consumes: current root README setup and architecture guidance
- Produces: accurate contributor guidance, no dead starter assets, and a detectable MIT license

- [ ] **Step 1: Confirm assets and broken skill paths are unreferenced**

Run: `rg -n 'file\.svg|globe\.svg|next\.svg|vercel\.svg|window\.svg|\.claude/skills' --glob '!frontend/public/*'`

Expected: only the stale `.claude/skills` table in `CLAUDE.md`; no application references to the SVG assets.

- [ ] **Step 2: Delete starter files**

Delete `frontend/README.md` and the five SVG files.

- [ ] **Step 3: Correct documentation**

Remove the obsolete `Development Phases` and `GitNexus MCP` sections from `CLAUDE.md`. In the README Development code block, retain the real pipeline, backfill, API, and frontend commands and remove these nonexistent-suite commands:

```text
uv run pytest
uv run pytest tests/test_cluster.py -k test_name
```

- [ ] **Step 4: Add the MIT license**

Create `LICENSE` using the canonical MIT text headed:

```text
MIT License

Copyright (c) 2026 icon3333
```

Include the standard permission, notice-preservation, and warranty-disclaimer paragraphs without alteration.

- [ ] **Step 5: Verify repository state**

Run: `rg -n 'file\.svg|globe\.svg|next\.svg|vercel\.svg|window\.svg|\.claude/skills|tests/test_cluster' --glob '!.git/**' || true`

Expected: no output.

Run: `python3 -m compileall -q narratio`

Expected: exit 0.

Run: `uv run python -c "import narratio.api, narratio.pipeline"`

Expected: both primary backend modules import without contacting external APIs.

Run: `cd frontend && npm run lint && npm run build`

Expected: ESLint and Next.js production build both exit 0.

Run: `git diff --check`

Expected: exit 0 with no output.

- [ ] **Step 6: Remove transient planning artifacts and commit**

Delete `docs/superpowers/`, then run:

```bash
git add -A
git commit -m "chore: remove stale repository scaffolding"
```

Expected: one non-behavioral cleanup commit.
