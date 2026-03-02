"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { fetchNarrativeDetail, fetchHeadlines, NarrativeDetail, Headline } from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function NarrativeDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [detail, setDetail] = useState<NarrativeDetail | null>(null);
  const [headlines, setHeadlines] = useState<Headline[]>([]);
  const [loading, setLoading] = useState(true);

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

  if (loading) return <div className="text-gray-500 text-center py-20">Loading...</div>;
  if (!detail) return <div className="text-red-400 text-center py-20">Narrative not found</div>;

  const latestWeek = detail.weeks[detail.weeks.length - 1];

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-gray-400 hover:text-gray-300">&larr; Back</Link>
        <h1 className="text-2xl font-bold">{detail.label}</h1>
        <span className={`px-2 py-0.5 rounded text-xs ${detail.status === "active" ? "bg-green-900/50 text-green-400" : "bg-gray-800 text-gray-500"}`}>
          {detail.status}
        </span>
      </div>

      {/* Metrics */}
      {latestWeek && (
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Share of Attention" value={`${latestWeek.share_of_attention?.toFixed(1)}%`} />
          <MetricCard label="Z-Score" value={latestWeek.z_score?.toFixed(2) ?? "N/A"} />
          <MetricCard label="Sentiment" value={latestWeek.sentiment_mean?.toFixed(2) ?? "N/A"} />
          <MetricCard label="Articles (latest)" value={String(latestWeek.article_count)} />
        </div>
      )}

      {/* Latest Summary */}
      {latestWeek?.summary && (
        <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-2">Latest Summary</h2>
          <p className="text-gray-200">{latestWeek.summary}</p>
        </div>
      )}

      {/* Sentiment Chart */}
      {detail.weeks.length > 1 && (
        <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-2">Sentiment Over Time</h2>
          <Plot
            data={[{
              x: detail.weeks.map((w) => w.week_start),
              y: detail.weeks.map((w) => w.sentiment_mean),
              type: "scatter",
              mode: "lines+markers",
              line: { color: "#60a5fa" },
              fill: "tozeroy",
            }]}
            layout={{
              height: 250,
              yaxis: { title: { text: "Sentiment" }, zeroline: true },
              xaxis: { title: { text: "Week" } },
              shapes: [{ type: "line", y0: 0, y1: 0, x0: 0, x1: 1, xref: "paper", line: { color: "gray", dash: "dash" } }],
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { color: "#d1d5db" },
              margin: { l: 50, r: 20, t: 10, b: 50 },
            }}
            config={{ responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Headlines */}
      <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
        <h2 className="text-sm font-semibold text-gray-400 mb-4">Top Headlines</h2>
        <div className="space-y-3">
          {headlines.map((h, i) => {
            const score = h.sentiment_score ?? 0;
            const icon = score > 0.2 ? "\u{1F7E2}" : score < -0.2 ? "\u{1F534}" : "\u26AA";
            const date = new Date(h.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
            return (
              <div key={i} className="flex items-start gap-2">
                <span>{icon}</span>
                <div>
                  <a href={h.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                    {h.headline}
                  </a>
                  <div className="text-xs text-gray-500">{h.source} &middot; {date}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Date range */}
      <div className="text-sm text-gray-500">
        Tracking since {detail.first_seen} &middot; Last seen {detail.last_seen}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}
