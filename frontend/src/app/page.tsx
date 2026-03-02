"use client";

import { useEffect, useRef, useState } from "react";
import TimelineChart from "@/components/TimelineChart";
import NarrativeTable from "@/components/NarrativeTable";
import ArticlesTab from "@/components/ArticlesTab";
import StatsTab from "@/components/StatsTab";
import {
  fetchNarratives,
  fetchTimeline,
  triggerPipeline,
  triggerAnalysis,
  fetchPipelineStatus,
  Narrative,
  TimelinePoint,
  PipelineStatus,
} from "@/lib/api";

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

type TabKey = "narratives" | "articles" | "stats";
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
  const [activeTab, setActiveTab] = useState<TabKey>("narratives");
  const [narratives, setNarratives] = useState<Narrative[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [mode, setMode] = useState<"attention" | "zscore">("attention");
  const [timeRange, setTimeRange] = useState<TimeRange>("1y");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>({
    running: false, last_result: null, step: 0, total_steps: 0, step_label: "",
  });
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pipelineRunning = pipelineStatus.running;
  const progressPct = pipelineStatus.total_steps > 0
    ? Math.round((pipelineStatus.step / pipelineStatus.total_steps) * 100)
    : 0;

  // Rank narratives by total article count across timeline points (most dominant first)
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
  const rankedLabels = [...labelTotals.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .filter(([, entry]) => [...entry.ids].some((id) => narrativeIds.has(id)))
    .slice(0, MAX_NARRATIVES)
    .map(([label, entry]) => ({ label, ids: entry.ids }));

  const [visibleCount, setVisibleCount] = useState(0);

  // Reset when available narratives change
  useEffect(() => {
    setVisibleCount(rankedLabels.length);
  }, [rankedLabels.length]);

  const visibleLabels = new Set(rankedLabels.slice(0, visibleCount).map((r) => r.label));
  const visibleIds = new Set(rankedLabels.slice(0, visibleCount).flatMap((r) => [...r.ids]));
  const filteredTimeline = timeline.filter((d) => visibleLabels.has(d.label));

  useEffect(() => {
    loadData();
  }, [timeRange]);

  // Cleanup polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  async function loadData() {
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
  }

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
      setPipelineStatus({ running: true, last_result: null, step: 0, total_steps: 11, step_label: "Starting..." });
      pollStatus();
    } catch (e) {
      console.error("Pipeline failed:", e);
    }
  }

  async function handleRunAnalysis() {
    try {
      const res = await triggerAnalysis();
      if (res.status === "already_running") return;
      setPipelineStatus({ running: true, last_result: null, step: 0, total_steps: 9, step_label: "Starting..." });
      pollStatus();
    } catch (e) {
      console.error("Analysis failed:", e);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Tab Bar */}
      <div className="tab-bar fade-up">
        {(["narratives", "articles", "stats"] as TabKey[]).map((tab) => (
          <button
            key={tab}
            className={activeTab === tab ? "tab-active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === "articles" && <ArticlesTab />}
      {activeTab === "stats" && <StatsTab />}

      {activeTab === "narratives" && error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            background: "var(--bg-error)",
            border: "1px solid var(--border-error)",
            borderRadius: 3,
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-error)",
          }}
        >
          {error}
        </div>
      )}
      {activeTab === "narratives" && (
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
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              {pipelineRunning ? (
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
                        {pipelineStatus.step_label}
                      </span>
                    </div>
                    <div style={{ height: 3, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${progressPct}%`, background: "var(--red)", borderRadius: 2, transition: "width 0.4s ease" }} />
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <PipelineButton onClick={handleRunAnalysis}>Re-analyze</PipelineButton>
                  <PipelineButton onClick={handleRunPipeline}>Update Data</PipelineButton>
                </>
              )}
            </div>
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
                  <div className="narrative-slider">
                    <label>
                      Showing {visibleCount} of {rankedLabels.length} narratives
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={rankedLabels.length}
                      value={visibleCount}
                      onChange={(e) => setVisibleCount(Number(e.target.value))}
                    />
                  </div>
                )}
                <TimelineChart data={filteredTimeline} mode={mode} />
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
