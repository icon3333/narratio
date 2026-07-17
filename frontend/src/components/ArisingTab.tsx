"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { fetchArising, ArisingNarrative } from "@/lib/api";
import { Th, Td } from "@/components/Table";

function Sparkline({ data, trend }: { data: number[]; trend: string }) {
  if (data.length === 0) return <span style={{ color: "var(--text-secondary)" }}>—</span>;

  const width = 64;
  const height = 24;
  const max = Math.max(...data, 1);
  const step = data.length > 1 ? width / (data.length - 1) : 0;

  const points = data.map((v, i) => ({
    x: data.length === 1 ? width / 2 : i * step,
    y: height - (v / max) * (height - 4) - 2,
  }));

  const pathD =
    points.length === 1
      ? `M${points[0].x - 4},${points[0].y}L${points[0].x + 4},${points[0].y}`
      : points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");

  const strokeColor =
    trend === "accelerating"
      ? "var(--sentiment-positive)"
      : trend === "fading"
        ? "var(--red)"
        : "var(--text-secondary)";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: "block" }}
    >
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Dot on the latest point */}
      {points.length > 0 && (
        <circle
          cx={points[points.length - 1].x}
          cy={points[points.length - 1].y}
          r={2}
          fill={strokeColor}
        />
      )}
    </svg>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const config = {
    accelerating: {
      label: "Accelerating",
      color: "var(--sentiment-positive)",
      bg: "rgba(91,117,83,0.1)",
    },
    steady: {
      label: "Steady",
      color: "var(--text-secondary)",
      bg: "var(--bg-badge-dormant)",
    },
    fading: {
      label: "Fading",
      color: "var(--red)",
      bg: "rgba(180,60,60,0.1)",
    },
  }[trend] || { label: trend, color: "var(--text-secondary)", bg: "var(--bg-badge-dormant)" };

  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.15rem 0.5rem",
        borderRadius: 3,
        fontSize: "0.68rem",
        fontWeight: 500,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        background: config.bg,
        color: config.color,
        opacity: trend === "fading" ? 0.6 : 1,
      }}
    >
      {config.label}
    </span>
  );
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

export default function ArisingTab() {
  const [data, setData] = useState<ArisingNarrative[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchArising()
      .then(setData)
      .catch(() => setError("Failed to load arising data."))
      .finally(() => setLoading(false));
  }, []);

  const fastestGrowing = useMemo(() => {
    if (data.length === 0) return null;
    return data.reduce((a, b) => {
      const aSlope = a.weekly_articles.length >= 2 ? a.weekly_articles[a.weekly_articles.length - 1] - a.weekly_articles[0] : 0;
      const bSlope = b.weekly_articles.length >= 2 ? b.weekly_articles[b.weekly_articles.length - 1] - b.weekly_articles[0] : 0;
      return bSlope > aSlope ? b : a;
    });
  }, [data]);

  const strongestSignal = useMemo(() => {
    if (data.length === 0) return null;
    return data.reduce((a, b) => ((b.latest_share ?? 0) > (a.latest_share ?? 0) ? b : a));
  }, [data]);

  if (loading) {
    return (
      <div className="fade-up" style={{ animationDelay: "0.08s" }}>
        <div className="stats-grid">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 100, borderRadius: 4 }} />
          ))}
        </div>
        <div className="skeleton" style={{ height: 400, borderRadius: 4 }} />
      </div>
    );
  }

  if (error || !data) {
    return <div className="error-box">{error || "No data available."}</div>;
  }

  return (
    <div className="fade-up" style={{ animationDelay: "0.08s" }}>
      {/* Summary Cards */}
      <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-label">Rising</div>
          <div className="stat-value">{data.length}</div>
          <div className="stat-sub">
            {data.length > 0
              ? `narrative${data.length !== 1 ? "s" : ""} arising`
              : "no new narratives"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Fastest Growing</div>
          <div className="stat-value" style={{ fontSize: "1rem" }}>
            {fastestGrowing ? truncate(fastestGrowing.label, 32) : "N/A"}
          </div>
          <div className="stat-sub">
            {fastestGrowing
              ? `${fastestGrowing.article_count_total} articles over ${fastestGrowing.weeks_active}w`
              : ""}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Strongest Signal</div>
          <div className="stat-value" style={{ fontSize: "1rem" }}>
            {strongestSignal ? truncate(strongestSignal.label, 32) : "N/A"}
          </div>
          <div className="stat-sub">
            {strongestSignal?.latest_share != null
              ? `${strongestSignal.latest_share.toFixed(1)}% attention`
              : ""}
          </div>
        </div>
      </div>

      {/* Arising Table */}
      <div
        style={{
          background: "var(--bg-card)",
          borderRadius: 3,
          boxShadow: "var(--card-shadow)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "1.5rem" }}>
          <h2
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.05rem",
              fontWeight: 400,
              marginBottom: "1rem",
              color: "var(--text-primary)",
            }}
          >
            Arising Narratives
          </h2>

          {data.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "2rem 1rem",
                color: "var(--text-secondary)",
                fontSize: "0.85rem",
              }}
            >
              No narratives with rising momentum detected.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <Th align="left" width={40}>#</Th>
                    <Th align="left">Narrative</Th>
                    <Th align="right">Age</Th>
                    <Th align="center">Trajectory</Th>
                    <Th align="right">Articles</Th>
                    <Th align="right">Attention</Th>
                    <Th align="center">Trend</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((n, i) => (
                    <tr
                      key={n.id}
                      className="narrative-row"
                      style={{ borderBottom: "1px solid var(--border-subtle)" }}
                    >
                      <Td align="left" style={{ color: "var(--text-secondary)", fontFamily: "var(--font-serif)", fontStyle: "italic" }}>
                        {i + 1}
                      </Td>
                      <Td align="left">
                        <Link
                          className="link-hover"
                          href={`/narratives/${n.id}`}
                          style={{
                            color: "var(--text-primary)",
                            textDecoration: "none",
                            fontWeight: 500,
                          }}
                        >
                          {n.label}
                        </Link>
                      </Td>
                      <Td align="right">
                        <span style={{ color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>
                          {n.weeks_active}w
                        </span>
                      </Td>
                      <Td align="center">
                        <Sparkline data={n.weekly_articles} trend={n.growth_trend} />
                      </Td>
                      <Td align="right" style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)" }}>
                        {n.article_count_total}
                      </Td>
                      <Td align="right" style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)" }}>
                        {n.latest_share != null ? `${n.latest_share.toFixed(1)}%` : "—"}
                      </Td>
                      <Td align="center">
                        <TrendBadge trend={n.growth_trend} />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
