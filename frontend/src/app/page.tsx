"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import TimelineChart from "@/components/TimelineChart";
import NarrativeTable from "@/components/NarrativeTable";
import ArticlesTab from "@/components/ArticlesTab";
import StatsTab from "@/components/StatsTab";
import ArisingTab from "@/components/ArisingTab";
import CoversTab from "@/components/CoversTab";
import MapTab from "@/components/MapTab";
import {
  fetchNarratives,
  fetchTimeline,
  fetchCovers,
  triggerPipeline,
  triggerAnalysis,
  fetchPipelineStatus,
  Narrative,
  TimelinePoint,
  PipelineStatus,
  Cover,
} from "@/lib/api";

// Must match PALETTE in TimelineChart.tsx
const NARRATIVE_PALETTE = [
  "#E3120B", "#1a6b8a", "#c4841d", "#5b7553", "#7b5ea7",
  "#d45d79", "#3d85c6", "#8c6d46", "#6b8e9b", "#b85c38",
  "#4a8c7f", "#9b6b9e",
];

function SkeletonChart() {
  return (
    <div style={{ padding: "1.5rem" }}>
      <div className="skeleton" style={{ height: 20, width: 140, marginBottom: 24 }} />
      <div className="skeleton" style={{ height: 340, width: "100%" }} />
    </div>
  );
}

function SkeletonTable() {
  return (
    <div style={{ padding: "1.5rem" }}>
      <div className="skeleton" style={{ height: 20, width: 180, marginBottom: 24 }} />
      {[...Array(5)].map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 44, width: "100%", marginBottom: 8, animationDelay: `${i * 0.1}s` }} />
      ))}
    </div>
  );
}

type TabKey = "arising" | "history" | "articles" | "map" | "covers" | "stats" | "settings";
type TimeRange = "all" | "1y" | "quarter" | "month";

function getTimeRangeParams(range: TimeRange): { start?: string } {
  if (range === "all") return {};
  const now = new Date();
  if (range === "1y") {
    const start = new Date(now);
    start.setFullYear(start.getFullYear() - 1);
    return { start: start.toISOString().slice(0, 10) };
  }
  if (range === "quarter") {
    const start = new Date(now);
    start.setMonth(start.getMonth() - 3);
    return { start: start.toISOString().slice(0, 10) };
  }
  // month = last 1 month
  const start = new Date(now);
  start.setMonth(start.getMonth() - 1);
  return { start: start.toISOString().slice(0, 10) };
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>("history");
  const [narratives, setNarratives] = useState<Narrative[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [mode, setMode] = useState<"attention" | "zscore">("attention");
  const [timeRange, setTimeRange] = useState<TimeRange>("quarter");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCovers, setShowCovers] = useState(false);
  const [allCovers, setAllCovers] = useState<Cover[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>({
    running: false, last_result: null, step: 0, total_steps: 0, step_label: "",
  });
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pipelineRunning = pipelineStatus.running;
  const progressPct = pipelineStatus.total_steps > 0
    ? Math.round((pipelineStatus.step / pipelineStatus.total_steps) * 100)
    : 0;

  // Rank narratives by total article count across timeline points (most dominant first)
  const rankedLabels = useMemo(() => {
    const labelTotals = new Map<string, { count: number; ids: Set<number> }>();
    timeline
      .filter((d) => d.label !== "Other")
      .forEach((d) => {
        const entry = labelTotals.get(d.label) || { count: 0, ids: new Set<number>() };
        entry.count += d.article_count;
        entry.ids.add(d.narrative_id);
        labelTotals.set(d.label, entry);
      });
    const MAX_NARRATIVES = 10;
    const narrativeIds = new Set(narratives.map((n) => n.id));
    return [...labelTotals.entries()]
      .sort((a, b) => b[1].count - a[1].count)
      .filter(([, entry]) => [...entry.ids].some((id) => narrativeIds.has(id)))
      .slice(0, MAX_NARRATIVES)
      .map(([label, entry]) => ({ label, ids: entry.ids }));
  }, [timeline, narratives]);

  const [hiddenLabels, setHiddenLabels] = useState<Set<string>>(new Set());

  // Reset when available narratives change
  useEffect(() => {
    setHiddenLabels(new Set());
  }, [rankedLabels.length]);

  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleChipClick = useCallback((label: string) => {
    if (clickTimerRef.current) {
      // Double-click detected — clear the pending single-click
      clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
      // Isolate: show only this label, hide all others
      setHiddenLabels((prev) => {
        const allLabels = rankedLabels.map((r) => r.label);
        const othersHidden = allLabels.filter((l) => l !== label).every((l) => prev.has(l));
        if (othersHidden) {
          // Already isolated — reset to show all
          return new Set();
        }
        return new Set(allLabels.filter((l) => l !== label));
      });
      return;
    }
    // Delay single-click to allow double-click detection
    clickTimerRef.current = setTimeout(() => {
      clickTimerRef.current = null;
      setHiddenLabels((prev) => {
        const next = new Set(prev);
        if (next.has(label)) next.delete(label);
        else next.add(label);
        return next;
      });
    }, 250);
  }, [rankedLabels]);

  const visibleLabels = useMemo(
    () => new Set(rankedLabels.filter((r) => !hiddenLabels.has(r.label)).map((r) => r.label)),
    [rankedLabels, hiddenLabels],
  );
  const visibleIds = useMemo(
    () => new Set(rankedLabels.filter((r) => !hiddenLabels.has(r.label)).flatMap((r) => [...r.ids])),
    [rankedLabels, hiddenLabels],
  );
  const filteredTimeline = useMemo(() => {
    // In attention mode, fold hidden narratives' share into "Other" to maintain 100% sum
    // In z-score mode, just filter normally (no stacking invariant)
    if (mode !== "attention" || hiddenLabels.size === 0) {
      return timeline.filter((d) => visibleLabels.has(d.label) || d.label === "Other");
    }

    // Group by week, accumulate hidden share into "Other"
    const weekMap = new Map<string, { other: TimelinePoint | null; hidden_sum: number }>();
    const visible: TimelinePoint[] = [];

    for (const d of timeline) {
      if (d.label !== "Other" && !visibleLabels.has(d.label) && !hiddenLabels.has(d.label)) continue;

      if (d.label === "Other" || hiddenLabels.has(d.label)) {
        let entry = weekMap.get(d.week_start);
        if (!entry) {
          entry = { other: null, hidden_sum: 0 };
          weekMap.set(d.week_start, entry);
        }
        if (d.label === "Other") {
          entry.other = d;
        } else {
          entry.hidden_sum += d.share_of_attention;
        }
      } else {
        visible.push(d);
      }
    }

    // Build merged "Other" rows
    const otherRows: TimelinePoint[] = [];
    for (const [week, entry] of weekMap) {
      if (entry.other) {
        otherRows.push({
          ...entry.other,
          share_of_attention: entry.other.share_of_attention + entry.hidden_sum,
        });
      } else if (entry.hidden_sum > 0) {
        // No backend "Other" row for this week — create one
        otherRows.push({
          narrative_id: -1,
          label: "Other",
          week_start: week,
          share_of_attention: entry.hidden_sum,
          z_score: null,
          article_count: 0,
          sentiment_mean: null,
        });
      }
    }

    return [...visible, ...otherRows];
  }, [timeline, visibleLabels, hiddenLabels, mode]);

  // Stable color registry: once a label gets a color, it keeps it for the session
  const stableColorRef = useRef<Record<string, string>>({});

  const colorMap = useMemo(() => {
    const map: Record<string, string> = {};
    const usedColors = new Set(Object.values(stableColorRef.current));

    rankedLabels.forEach((r) => {
      if (stableColorRef.current[r.label]) {
        map[r.label] = stableColorRef.current[r.label];
      } else {
        let colorIdx = 0;
        while (usedColors.has(NARRATIVE_PALETTE[colorIdx % NARRATIVE_PALETTE.length]) && colorIdx < NARRATIVE_PALETTE.length) {
          colorIdx++;
        }
        const color = NARRATIVE_PALETTE[colorIdx % NARRATIVE_PALETTE.length];
        map[r.label] = color;
        stableColorRef.current[r.label] = color;
        usedColors.add(color);
      }
    });

    return map;
  }, [rankedLabels]);

  // Filter covers to current time range
  const visibleCovers = (() => {
    if (!showCovers || allCovers.length === 0) return undefined;
    const rangeParams = getTimeRangeParams(timeRange);
    const startDate = rangeParams.start ? new Date(rangeParams.start) : null;
    return allCovers.filter((c) => {
      if (!startDate) return true;
      return new Date(c.date) >= startDate;
    });
  })();
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = getTimeRangeParams(timeRange);
      const [n, t] = await Promise.all([fetchNarratives(), fetchTimeline(params)]);
      setNarratives(n);
      setTimeline(t);
    } catch (e) {
      console.error("Failed to load data:", e);
      setError("Failed to load dashboard data. Is the API running?");
    }
    setLoading(false);
  }, [timeRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Fetch all covers when toggle is turned on
  useEffect(() => {
    if (!showCovers || allCovers.length > 0) return;
    fetchCovers(undefined, 1, 500)
      .then((res) => setAllCovers(res.covers))
      .catch((err) => console.error("Cover fetch failed:", err));
  }, [showCovers, allCovers.length]);

  // Cleanup polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  function pollStatus() {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    const interval = setInterval(async () => {
      try {
        const status = await fetchPipelineStatus();
        setPipelineStatus(status);
        if (!status.running) {
          clearInterval(interval);
          pollIntervalRef.current = null;
          loadData();
        }
      } catch {
        clearInterval(interval);
        pollIntervalRef.current = null;
        setPipelineStatus((s) => ({ ...s, running: false }));
      }
    }, 1500);
    pollIntervalRef.current = interval;
  }

  async function handleRunPipeline() {
    try {
      const res = await triggerPipeline();
      if (res.status === "already_running") return;
      setPipelineStatus({ running: true, last_result: null, step: 0, total_steps: 13, step_label: "Starting..." });
      pollStatus();
    } catch (e) {
      console.error("Pipeline failed:", e);
    }
  }

  async function handleRunAnalysis() {
    try {
      const res = await triggerAnalysis();
      if (res.status === "already_running") return;
      setPipelineStatus({ running: true, last_result: null, step: 0, total_steps: 10, step_label: "Starting..." });
      pollStatus();
    } catch (e) {
      console.error("Analysis failed:", e);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Tab Bar */}
      <div className="tab-bar fade-up">
        {(["history", "arising", "articles", "map", "covers", "stats"] as TabKey[]).map((tab) => (
          <button
            key={tab}
            className={activeTab === tab ? "tab-active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
        <button
          className={activeTab === "settings" ? "tab-active" : ""}
          onClick={() => setActiveTab("settings")}
          style={{ marginLeft: "auto" }}
        >
          Settings
        </button>
      </div>

      {activeTab === "arising" && <ArisingTab />}
      {activeTab === "articles" && <ArticlesTab />}
      {activeTab === "map" && <MapTab />}
      {activeTab === "covers" && <CoversTab />}
      {activeTab === "stats" && <StatsTab />}
      {activeTab === "settings" && (
        <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Pipeline section */}
          <div style={{
            background: "var(--bg-card)",
            borderRadius: 3,
            boxShadow: "var(--card-shadow)",
            padding: "1.5rem",
          }}>
            <h2 style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.05rem",
              fontWeight: 400,
              marginBottom: "0.25rem",
              color: "var(--text-primary)",
            }}>
              Pipeline
            </h2>
            <p style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.78rem",
              color: "var(--text-secondary)",
              marginBottom: "1rem",
              lineHeight: 1.5,
            }}>
              Re-analyze runs the 9-step analysis on existing articles. Update Data also ingests new articles first.
            </p>
            {pipelineRunning ? (
              <PipelineProgress progressPct={progressPct} stepLabel={pipelineStatus.step_label} />
            ) : (
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <PipelineButton onClick={handleRunAnalysis}>Re-analyze</PipelineButton>
                <PipelineButton onClick={handleRunPipeline}>Update Data</PipelineButton>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "history" && error && (
        <div className="error-box">{error}</div>
      )}
      {activeTab === "history" && (
        <>
          {/* Controls */}
          <div
            className="fade-up"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <ModeButton active={mode === "attention"} onClick={() => setMode("attention")}>
                Share of Attention
              </ModeButton>
              <ModeButton active={mode === "zscore"} onClick={() => setMode("zscore")}>
                Z-Score Anomaly
              </ModeButton>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <ModeButton active={timeRange === "all"} onClick={() => setTimeRange("all")}>
                All
              </ModeButton>
              <ModeButton active={timeRange === "1y"} onClick={() => setTimeRange("1y")}>
                1 Year
              </ModeButton>
              <ModeButton active={timeRange === "quarter"} onClick={() => setTimeRange("quarter")}>
                Quarter
              </ModeButton>
              <ModeButton active={timeRange === "month"} onClick={() => setTimeRange("month")}>
                Month
              </ModeButton>
              <div style={{ borderLeft: "1px solid var(--border)", paddingLeft: "0.5rem", marginLeft: "0.25rem", display: "flex", alignItems: "center" }}>
                <ToggleSwitch checked={showCovers} onChange={() => setShowCovers((v) => !v)}>
                  Covers
                </ToggleSwitch>
              </div>
            </div>
            {pipelineRunning && (
              <PipelineProgress progressPct={progressPct} stepLabel={pipelineStatus.step_label} />
            )}
          </div>

          {/* Timeline Chart */}
          <div
            className="fade-up"
            style={{
              background: "var(--bg-card)",
              borderRadius: 3,
              boxShadow: "var(--card-shadow)",
              overflow: "hidden",
              animationDelay: "0.08s",
            }}
          >
            {loading ? (
              <SkeletonChart />
            ) : (
              <div style={{ padding: "1.5rem" }}>
                <h2 style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: "1.05rem",
                  fontWeight: 400,
                  marginBottom: "1rem",
                  color: "var(--text-primary)",
                }}>
                  {mode === "attention" ? "Share of Attention" : "Z-Score Anomaly Detection"}
                </h2>
                {rankedLabels.length > 1 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", alignItems: "center", marginBottom: "0.75rem" }}>
                    {rankedLabels.map((r) => {
                      const hidden = hiddenLabels.has(r.label);
                      const color = colorMap[r.label] ?? NARRATIVE_PALETTE[0];
                      return (
                        <button
                          key={r.label}
                          onClick={() => handleChipClick(r.label)}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            padding: "0.2rem 0.5rem",
                            border: "1px solid var(--border)",
                            borderRadius: 12,
                            background: hidden ? "transparent" : "var(--bg-card)",
                            opacity: hidden ? 0.4 : 1,
                            cursor: "pointer",
                            fontFamily: "var(--font-sans)",
                            fontSize: "0.68rem",
                            color: "var(--text-secondary)",
                            lineHeight: 1.3,
                            transition: "opacity 0.15s ease",
                          }}
                        >
                          <span style={{
                            width: 7,
                            height: 7,
                            borderRadius: "50%",
                            background: color,
                            flexShrink: 0,
                            opacity: hidden ? 0.3 : 1,
                          }} />
                          {r.label}
                        </button>
                      );
                    })}
                    {hiddenLabels.size > 0 && (
                      <button
                        onClick={() => setHiddenLabels(new Set())}
                        style={{
                          padding: "0.2rem 0.5rem",
                          border: "none",
                          borderRadius: 12,
                          background: "none",
                          cursor: "pointer",
                          fontFamily: "var(--font-sans)",
                          fontSize: "0.68rem",
                          color: "var(--red)",
                          fontWeight: 500,
                        }}
                      >
                        Show all
                      </button>
                    )}
                  </div>
                )}
                <TimelineChart data={filteredTimeline} mode={mode} covers={visibleCovers} colorMap={colorMap} />
              </div>
            )}
          </div>

          {/* Narrative Table */}
          <div
            className="fade-up"
            style={{
              background: "var(--bg-card)",
              borderRadius: 3,
              boxShadow: "var(--card-shadow)",
              overflow: "hidden",
              animationDelay: "0.16s",
            }}
          >
            {loading ? (
              <SkeletonTable />
            ) : (
              <div style={{ padding: "1.5rem" }}>
                <h2 style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: "1.05rem",
                  fontWeight: 400,
                  marginBottom: "1rem",
                  color: "var(--text-primary)",
                }}>
                  Discovered Narratives
                </h2>
                <NarrativeTable
                  narratives={narratives}
                  topIds={visibleIds}
                />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function PipelineButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      className="btn-pipeline"
      onClick={onClick}
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
        cursor: "pointer",
        letterSpacing: "0.03em",
      }}
    >
      {children}
    </button>
  );
}

function ToggleSwitch({ checked, onChange, children }: { checked: boolean; onChange: () => void; children: React.ReactNode }) {
  return (
    <label className="toggle-switch" style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer" }}>
      <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", fontWeight: 500, color: checked ? "var(--red)" : "var(--text-secondary)", letterSpacing: "0.03em" }}>
        {children}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={`toggle-track${checked ? " toggle-track--on" : ""}`}
      />
    </label>
  );
}

function PipelineProgress({ progressPct, stepLabel }: { progressPct: number; stepLabel: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: "spin 0.8s linear infinite", flexShrink: 0 }}>
        <polyline points="23 4 23 10 17 10" />
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: 140 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", fontWeight: 500, color: "var(--text-primary)", letterSpacing: "0.03em" }}>
            {progressPct}%
          </span>
          <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--text-secondary)" }}>
            {stepLabel}
          </span>
        </div>
        <div style={{ height: 3, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${progressPct}%`, background: "var(--red)", borderRadius: 2, transition: "width 0.4s ease" }} />
        </div>
      </div>
    </div>
  );
}

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      className={`btn-mode${active ? " btn-mode--active" : ""}`}
      onClick={onClick}
      style={{
        background: "none",
        border: active ? "1.5px solid var(--red)" : "1.5px solid var(--border)",
        borderRadius: 6,
        padding: "0.5rem 0.85rem",
        fontFamily: "var(--font-sans)",
        fontSize: "0.75rem",
        fontWeight: 500,
        color: active ? "var(--red)" : "var(--text-secondary)",
        cursor: "pointer",
        letterSpacing: "0.03em",
      }}
    >
      {children}
    </button>
  );
}
