"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchStats, Stats } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function StatsTab() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setError("Failed to load stats."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="fade-up" style={{ animationDelay: "0.08s" }}>
        <div className="stats-grid">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 100, borderRadius: 4 }} />
          ))}
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 180, marginBottom: 16, borderRadius: 4 }} />
        ))}
      </div>
    );
  }

  if (error || !stats) {
    return <div className="error-box">{error || "No data available."}</div>;
  }

  const noiseRatio = stats.total_articles > 0
    ? ((stats.noise_count / stats.total_articles) * 100).toFixed(1)
    : "0";

  return (
    <div className="fade-up" style={{ animationDelay: "0.08s" }}>
      {/* Overview Counters */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Articles</div>
          <div className="stat-value">{stats.total_articles.toLocaleString()}</div>
          {stats.sources_breakdown.length > 0 && (
            <div className="stat-sub">
              {stats.sources_breakdown.map((s) => `${s.source}: ${s.count.toLocaleString()}`).join(" / ")}
            </div>
          )}
        </div>
        <div className="stat-card">
          <div className="stat-label">Narratives</div>
          <div className="stat-value">{stats.total_narratives}</div>
          <div className="stat-sub">
            {stats.active_narratives} active / {stats.dormant_narratives} dormant
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Date Range</div>
          <div className="stat-value" style={{ fontSize: "1rem" }}>
            {stats.first_article_date ? formatDate(stats.first_article_date) : "N/A"}
          </div>
          <div className="stat-sub">
            {stats.last_article_date ? `to ${formatDate(stats.last_article_date)}` : ""}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Noise Ratio</div>
          <div className="stat-value">{noiseRatio}%</div>
          <div className="stat-sub">
            {stats.noise_count.toLocaleString()} unassigned articles
          </div>
        </div>
      </div>

      {/* Leaderboards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
        <LeaderboardCard title="Top by Significance">
          <MiniTable
            headers={["Narrative", "Score"]}
            rows={stats.top_by_significance.map((n) => ({
              id: n.id,
              label: n.label,
              value: n.significance_score.toFixed(3),
            }))}
          />
        </LeaderboardCard>

        <LeaderboardCard title="Biggest Movers (This Week)">
          <MiniTable
            headers={["Narrative", "Z-Score"]}
            rows={stats.biggest_movers.map((n) => ({
              id: n.id,
              label: n.label,
              value: n.z_score >= 0 ? `+${n.z_score.toFixed(2)}` : n.z_score.toFixed(2),
            }))}
          />
        </LeaderboardCard>

        <LeaderboardCard title="Longest Running">
          <MiniTable
            headers={["Narrative", "Duration"]}
            rows={stats.longest_running.map((n) => ({
              id: n.id,
              label: n.label,
              value: `${Math.round(n.duration_days / 7)}w`,
            }))}
          />
        </LeaderboardCard>
      </div>
    </div>
  );
}

function LeaderboardCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderRadius: 3,
        boxShadow: "var(--card-shadow)",
        padding: "1.25rem",
      }}
    >
      <h3
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: "0.95rem",
          fontWeight: 400,
          color: "var(--text-primary)",
          marginBottom: "0.75rem",
        }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

function MiniTable({
  headers,
  rows,
}: {
  headers: [string, string];
  rows: { id: number; label: string; value: string }[];
}) {
  if (rows.length === 0) {
    return (
      <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", padding: "0.5rem 0" }}>
        No data yet.
      </div>
    );
  }

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
      <thead>
        <tr style={{ borderBottom: "1px solid var(--border)" }}>
          <th
            style={{
              textAlign: "left",
              padding: "0.4rem 0.5rem",
              fontWeight: 500,
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-secondary)",
            }}
          >
            {headers[0]}
          </th>
          <th
            style={{
              textAlign: "right",
              padding: "0.4rem 0.5rem",
              fontWeight: 500,
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-secondary)",
            }}
          >
            {headers[1]}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="narrative-row" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
            <td style={{ padding: "0.5rem 0.5rem" }}>
              <Link
                href={`/narratives/${r.id}`}
                className="link-hover"
                style={{ color: "var(--text-primary)", textDecoration: "none", fontWeight: 500 }}
              >
                {r.label}
              </Link>
            </td>
            <td
              style={{
                textAlign: "right",
                padding: "0.5rem 0.5rem",
                fontVariantNumeric: "tabular-nums",
                color: "var(--text-secondary)",
              }}
            >
              {r.value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
