#!/usr/bin/env bash
trap 'kill 0' EXIT

# Free ports if occupied
lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti :3000 2>/dev/null | xargs kill -9 2>/dev/null

# Remove stale Next.js lock
rm -f frontend/.next/dev/lock

uv run uvicorn narratio.api:app --reload --port 8000 &
cd frontend && npm run dev -- --port 3000 &
wait
