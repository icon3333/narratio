"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchCovers, refreshCovers, coverImageUrl, Cover, CoversResponse } from "@/lib/api";

function SkeletonGrid() {
  return (
    <div className="covers-grid">
      {[...Array(8)].map((_, i) => (
        <div key={i} className="cover-skeleton" style={{ animationDelay: `${i * 0.05}s` }}>
          <div className="cover-skeleton-img skeleton" />
          <div className="cover-skeleton-text skeleton" />
        </div>
      ))}
    </div>
  );
}

export default function CoversTab() {
  const [covers, setCovers] = useState<Cover[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [zoomState, setZoomState] = useState<{ id: number; transform: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadCovers = useCallback(async (year?: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCovers(year);
      setCovers(res.covers);
      if (res.years.length > 0) {
        setYears(res.years);
      }
    } catch (e) {
      console.error("Failed to load covers:", e);
      setError("Failed to load covers. Is the API running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadCovers(selectedYear);
  }, [selectedYear, loadCovers]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshCovers(selectedYear);
      // Poll briefly then reload
      await new Promise((r) => setTimeout(r, 3000));
      await loadCovers(selectedYear);
    } catch (e) {
      console.error("Refresh failed:", e);
    }
    setRefreshing(false);
  }

  function handleCardClick(cover: Cover, e: React.MouseEvent<HTMLDivElement>) {
    if (zoomState?.id === cover.id) {
      setZoomState(null);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    const cardCenterX = rect.left + rect.width / 2;
    const cardCenterY = rect.top + rect.height / 2;
    const vpCenterX = window.innerWidth / 2;
    const vpCenterY = window.innerHeight / 2;
    const tx = vpCenterX - cardCenterX;
    const ty = vpCenterY - cardCenterY;
    setZoomState({ id: cover.id, transform: `translate(${tx}px, ${ty}px) scale(2.5)` });
  }

  function formatDate(dateStr: string) {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  return (
    <div className="fade-up">
      {/* Header */}
      <div className="covers-header">
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <h2
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.05rem",
              fontWeight: 400,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            Economist Covers
          </h2>
          {years.length > 0 && (
            <select
              value={selectedYear ?? ""}
              onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : undefined)}
            >
              <option value="">All Years</option>
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          )}
        </div>
        <button
          className="btn-pipeline"
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            background: "none",
            border: "1.5px solid",
            borderRadius: 6,
            padding: "0.5rem 0.85rem",
            fontFamily: "var(--font-sans)",
            fontSize: "0.75rem",
            fontWeight: 500,
            cursor: refreshing ? "default" : "pointer",
            letterSpacing: "0.03em",
            opacity: refreshing ? 0.6 : 1,
          }}
        >
          {refreshing ? (
            <>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ animation: "spin 0.8s linear infinite" }}
              >
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              Scraping...
            </>
          ) : (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              Refresh
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            background: "var(--bg-error)",
            border: "1px solid var(--border-error)",
            borderRadius: 3,
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-error)",
            marginBottom: "1.5rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <SkeletonGrid />
      ) : covers.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "3rem 1rem",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-sans)",
            fontSize: "0.85rem",
          }}
        >
          No covers found. Click Refresh to scrape from The Economist.
        </div>
      ) : (
        <div className="covers-grid">
          {covers.map((cover) => (
            <div
              key={cover.id}
              className={`cover-card${zoomState?.id === cover.id ? " cover-card--zoomed" : ""}`}
              onClick={(e) => handleCardClick(cover, e)}
              style={zoomState?.id === cover.id ? { transform: zoomState.transform } : undefined}
            >
              <img
                src={coverImageUrl(cover.image_url)}
                alt={cover.title || `Economist cover ${cover.date}`}
                loading="lazy"
              />
              <div className="cover-info">
                <span className="cover-date">{formatDate(cover.date)}</span>
                {cover.edition_url && (
                  <a
                    href={cover.edition_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="cover-link"
                    onClick={(e) => e.stopPropagation()}
                    title="View edition on The Economist"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Backdrop for zoomed card */}
      {zoomState !== null && (
        <div className="cover-backdrop" onClick={() => setZoomState(null)} />
      )}
    </div>
  );
}
