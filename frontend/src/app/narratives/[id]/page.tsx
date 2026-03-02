"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { fetchNarrativeDetail, fetchHeadlines, NarrativeDetail, Headline } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

function SkeletonDetail() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div className="skeleton" style={{ height: 28, width: 260 }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 80, animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
      <div className="skeleton" style={{ height: 200 }} />
      <div className="skeleton" style={{ height: 280 }} />
    </div>
  );
}

export default function NarrativeDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [detail, setDetail] = useState<NarrativeDetail | null>(null);
  const [headlines, setHeadlines] = useState<Headline[]>([]);
  const [loading, setLoading] = useState(true);
  const { theme } = useTheme();

  useEffect(() => {
    async function load() {
      try {
        const [d, h] = await Promise.all([
          fetchNarrativeDetail(id),
          fetchHeadlines(id, 10),
        ]);
        setDetail(d);
        setHeadlines(h);
      } catch (e) {
        console.error("Failed to load narrative:", e);
      }
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) return <SkeletonDetail />;

  if (!detail) {
    return (
      <div style={{ textAlign: "center", padding: "4rem 1rem", color: "var(--red)", fontSize: "0.9rem" }}>
        Narrative not found.
      </div>
    );
  }

  const latestWeek = detail.weeks[detail.weeks.length - 1];

  return (
    <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
        <Link
          className="link-hover"
          href="/"
          style={{
            color: "var(--text-secondary)",
            textDecoration: "none",
            fontSize: "0.82rem",
          }}
        >
          &larr; Back
        </Link>
        <h1 style={{
          fontFamily: "var(--font-serif)",
          fontSize: "1.5rem",
          fontWeight: 700,
          color: "var(--text-primary)",
          lineHeight: 1.2,
        }}>
          {detail.label}
        </h1>
        <span style={{
          display: "inline-block",
          padding: "0.15rem 0.5rem",
          borderRadius: 3,
          fontSize: "0.7rem",
          fontWeight: 500,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          background: detail.status === "active" ? "var(--bg-badge-active)" : "var(--bg-badge-dormant)",
          color: detail.status === "active" ? "var(--red)" : "var(--text-secondary)",
        }}>
          {detail.status}
        </span>
      </div>

      {/* Metric Cards */}
      {latestWeek && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem" }}>
          <MetricCard label="Share of Attention" value={`${latestWeek.share_of_attention?.toFixed(1) ?? "—"}%`} />
          <MetricCard label="Z-Score" value={latestWeek.z_score?.toFixed(2) ?? "N/A"} highlight={Math.abs(latestWeek.z_score ?? 0) >= 2} />
          <MetricCard label="Sentiment" value={latestWeek.sentiment_mean?.toFixed(2) ?? "N/A"} />
          <MetricCard label="Articles (latest)" value={String(latestWeek.article_count)} />
        </div>
      )}

      {/* Latest Summary */}
      {latestWeek?.summary && (
        <div style={{
          background: "var(--bg-card)",
          borderRadius: 3,
          boxShadow: "var(--card-shadow)",
          padding: "1.25rem 1.5rem",
        }}>
          <div style={{
            fontSize: "0.7rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--text-secondary)",
            fontWeight: 500,
            marginBottom: "0.5rem",
          }}>
            Latest Summary
          </div>
          <p style={{
            fontFamily: "var(--font-serif)",
            fontSize: "0.95rem",
            lineHeight: 1.65,
            color: "var(--text-primary)",
            fontStyle: "italic",
          }}>
            {latestWeek.summary}
          </p>
        </div>
      )}

      {/* Sentiment Chart */}
      {detail.weeks.length > 1 && (
        <div style={{
          background: "var(--bg-card)",
          borderRadius: 3,
          boxShadow: "var(--card-shadow)",
          padding: "1.5rem",
        }}>
          <div style={{
            fontSize: "0.7rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--text-secondary)",
            fontWeight: 500,
            marginBottom: "1rem",
          }}>
            Sentiment Over Time
          </div>
          <Plot
            data={[{
              x: detail.weeks.map((w) => w.week_start),
              y: detail.weeks.map((w) => w.sentiment_mean),
              type: "scatter",
              mode: "lines+markers",
              line: { color: theme === "dark" ? "#ef4444" : "#E3120B", width: 2 },
              marker: { size: 5, color: theme === "dark" ? "#ef4444" : "#E3120B" },
              fill: "tozeroy",
              fillcolor: theme === "dark" ? "rgba(239,68,68,0.1)" : "rgba(227,18,11,0.06)",
              hovertemplate: "Sentiment: %{y:.2f}<extra></extra>",
            }]}
            layout={{
              height: 220,
              yaxis: {
                title: { text: "Sentiment", font: { size: 11, color: theme === "dark" ? "#a8a29e" : "#999" } },
                zeroline: true,
                zerolinecolor: theme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)",
                gridcolor: theme === "dark" ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)",
                tickfont: { size: 10, color: theme === "dark" ? "#a8a29e" : "#999" },
              },
              xaxis: {
                gridcolor: theme === "dark" ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)",
                tickfont: { size: 10, color: theme === "dark" ? "#a8a29e" : "#999" },
              },
              shapes: [{
                type: "line", y0: 0, y1: 0, x0: 0, x1: 1, xref: "paper",
                line: { color: theme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)", dash: "dash", width: 1 },
              }],
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { family: "'DM Sans', sans-serif", color: theme === "dark" ? "#f5f0eb" : "#1a1a1a", size: 11 },
              hoverlabel: {
                bgcolor: theme === "dark" ? "#292524" : "#ffffff",
                bordercolor: theme === "dark" ? "#44403c" : "#e8e5e1",
                font: {
                  color: theme === "dark" ? "#f5f0eb" : "#1a1a1a",
                  family: "'DM Sans', sans-serif",
                  size: 11,
                },
              },
              margin: { l: 50, r: 16, t: 8, b: 40 },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Headlines */}
      <div style={{
        background: "var(--bg-card)",
        borderRadius: 3,
        boxShadow: "var(--card-shadow)",
        padding: "1.5rem",
      }}>
        <div style={{
          fontSize: "0.7rem",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "var(--text-secondary)",
          fontWeight: 500,
          marginBottom: "1rem",
        }}>
          Top Headlines
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {headlines.length === 0 && (
            <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>No headlines available.</div>
          )}
          {headlines.map((h, i) => {
            const score = h.sentiment_score ?? 0;
            const dotColor = score > 0.2 ? "var(--sentiment-positive)" : score < -0.2 ? "var(--sentiment-negative)" : "var(--sentiment-neutral)";
            const date = new Date(h.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "0.75rem",
                  paddingBottom: i < headlines.length - 1 ? "0.75rem" : 0,
                  borderBottom: i < headlines.length - 1 ? "1px solid var(--border-subtle)" : "none",
                }}
              >
                <div style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: dotColor,
                  marginTop: 7,
                  flexShrink: 0,
                }} />
                <div>
                  <a
                    className="link-hover"
                    href={h.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: "var(--text-primary)",
                      textDecoration: "none",
                      fontSize: "0.85rem",
                      fontWeight: 400,
                      lineHeight: 1.4,
                    }}
                  >
                    {h.headline}
                  </a>
                  <div style={{
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                    marginTop: "0.15rem",
                  }}>
                    {h.source} &middot; {date}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer date range */}
      <div style={{
        fontSize: "0.75rem",
        color: "var(--text-secondary)",
        fontStyle: "italic",
        fontFamily: "var(--font-serif)",
      }}>
        Tracking since {formatDate(detail.first_seen)} &middot; Last seen {formatDate(detail.last_seen)}
      </div>
    </div>
  );
}

function MetricCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{
      background: "var(--bg-card)",
      borderRadius: 3,
      boxShadow: "var(--card-shadow)",
      padding: "1rem 1.25rem",
      position: "relative",
      overflow: "hidden",
    }}>
      {highlight && (
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: "var(--red)",
        }} />
      )}
      <div style={{
        fontSize: "0.7rem",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "var(--text-secondary)",
        fontWeight: 500,
        marginBottom: "0.35rem",
      }}>
        {label}
      </div>
      <div style={{
        fontSize: "1.5rem",
        fontFamily: "var(--font-serif)",
        fontWeight: 700,
        color: "var(--text-primary)",
      }}>
        {value}
      </div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}
