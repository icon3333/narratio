# Narratio Code Review — Critical Issues & Quick Wins

**Date:** 2026-03-18
**Scope:** Full backend + frontend audit

---

## Critical Issues & Errors

### 1. SSRF via Image Proxy
**File:** `narratio/api.py:338-339`
**Severity:** CRITICAL (Security)

The cover image proxy only checks `"economist.com" in url`, which is trivially bypassed with `https://evil.com?economist.com`. An attacker can use your server as an open proxy to fetch arbitrary URLs.

**Fix:** Validate the URL's hostname strictly:
```python
from urllib.parse import urlparse
if urlparse(url).hostname not in ("www.economist.com", "economist.com"):
    raise HTTPException(400, "Invalid image URL")
```

---

### 2. DB Committed Before Numpy File Saved
**File:** `narratio/embed.py:93-98`
**Severity:** CRITICAL (Data Integrity)

Database embedding indices are committed (line 97) before `np.save()` (line 98). If the numpy save fails (disk full, permissions), the DB points to embedding indices that don't exist in the `.npy` file. All downstream clustering/labeling will read corrupt data.

**Fix:** Save numpy first, then commit DB. Or wrap both in a try/except that rolls back the DB on numpy save failure.

---

### 3. Transaction Fragmentation in Labeling
**File:** `narratio/label.py:89-205`
**Severity:** CRITICAL (Data Integrity)

`label_clusters()` calls `conn.commit()` inside the loop (lines 91, 144, 189) and again after (199, 205). If an LLM call fails mid-loop, some articles are assigned to narratives and committed while others aren't. The database is left in an inconsistent half-labeled state.

**Fix:** Remove mid-loop commits. Do one commit at the end after all clusters are processed.

---

### 4. Guardian Ingestion Has No Error Handling
**File:** `narratio/ingest_guardian.py:39`
**Severity:** HIGH (Reliability)

`resp.raise_for_status()` will crash the entire ingestion if any page request fails. No retry logic, no connection cleanup on failure (conn opened at line 80 leaks). Compare with NYT ingest which has 3-retry logic with exponential backoff.

**Fix:** Add retry logic matching `ingest.py:_fetch_archive()`, and wrap `ingest_month` in try/finally for connection cleanup.

---

### 5. Incorrect Centroid Index Stored
**File:** `narratio/label.py:153, 176`
**Severity:** HIGH (Correctness)

`centroid_embedding_index` is set to `idx_list[0]` (the first article's embedding), not the actual centroid. The centroid is computed on line 122 (`new_centroid = c_vecs.mean(axis=0)`) but never stored. This means narrative similarity matching on subsequent runs uses an article embedding instead of the true centroid.

**Fix:** Store the centroid embedding in the numpy array and use its index, or compute centroids dynamically from article indices.

---

### 6. `Math.min(...[])` Crash in Timeline Chart
**File:** `frontend/src/components/TimelineChart.tsx:109-110`
**Severity:** HIGH (Runtime Error)

When `filtered` is empty, `Math.min()` returns `Infinity` and `Math.max()` returns `-Infinity`. This produces `NaN` in all downstream calculations, crashing the chart.

**Fix:** Guard with early return:
```typescript
if (allDates.length === 0) return { minDate: 0, maxDate: 0, dateSpan: 1 };
```

---

### 7. Entire Test Suite Deleted
**Severity:** HIGH (Quality)

Commit `82d5d32` (Mar 4, 2026) removed all 1,514 lines of tests across 12 files. `uv run pytest` has nothing to run, despite CLAUDE.md and README still documenting test commands.

---

## High-Impact / Low-Effort Improvements

### 1. Add `try/finally` to All DB-Using Functions
Multiple functions (`ingest.py:88`, `ingest_guardian.py:80`, `label.py:68`) open connections without `try/finally`. A single exception leaks the connection.

**Effort:** ~30 min | **Impact:** Prevents connection leaks and WAL lock issues

---

### 2. Batch Z-Score Updates
**File:** `narratio/summarize.py:245-275`

Currently does one `UPDATE` per narrative per week inside nested loops. For 50 narratives × 30 weeks = 1,500 individual UPDATE statements. Use `executemany()` with a list of pre-computed values.

**Effort:** ~15 min | **Impact:** 10-50x faster z-score computation

---

### 3. Remove N+1 Query in Label Loop
**File:** `narratio/label.py:113-116`

Each cluster triggers an individual `SELECT embedding_index` query. Phase 1 already batch-fetches indices for existing narratives (lines 75-80). Apply the same pattern for clusters.

**Effort:** ~20 min | **Impact:** Eliminates N queries (one per cluster)

---

### 4. Add Date Validation to API Endpoints
**File:** `narratio/api.py:147, 165-170`

`start` and `end` query params go straight to SQL without format validation. While parameterized queries prevent injection, invalid dates cause confusing 500 errors.

**Effort:** ~10 min | **Impact:** Better error messages, prevents confusing failures

---

### 5. Fix Silent Fetch Failures in Frontend
Three places swallow API errors with `.catch(() => {})`:
- `frontend/src/components/ArticlesTab.tsx:40` — sources fetch
- `frontend/src/components/MapTab.tsx:259` — date range fetch
- `frontend/src/app/page.tsx:269-274` — covers fetch

**Effort:** ~15 min | **Impact:** Users actually see when something breaks

---

### 6. Restore Test Suite
The deleted tests covered all critical modules. Recovering them from git history (`git show eb5550d:tests/`) is straightforward.

**Effort:** ~30 min (recover + verify) | **Impact:** Prevents regressions across the entire pipeline

---

## Summary Priority Matrix

| Priority | Issue | Type | Effort |
|----------|-------|------|--------|
| P0 | SSRF via image proxy | Security | 5 min |
| P0 | DB commit before numpy save | Data Integrity | 10 min |
| P0 | Transaction fragmentation in labeling | Data Integrity | 15 min |
| P1 | Guardian ingestion no retries/cleanup | Reliability | 20 min |
| P1 | Wrong centroid index stored | Correctness | 20 min |
| P1 | Timeline chart empty array crash | Runtime Error | 5 min |
| P1 | Restore test suite | Quality | 30 min |
| P2 | try/finally on all DB functions | Resource Leak | 30 min |
| P2 | Batch z-score updates | Performance | 15 min |
| P2 | N+1 query in label loop | Performance | 20 min |
| P2 | Date validation on API | Robustness | 10 min |
| P2 | Silent frontend fetch failures | UX | 15 min |
