"use client";

import dynamic from "next/dynamic";
import { TimelinePoint } from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Props {
  data: TimelinePoint[];
  mode: "attention" | "zscore";
}

export default function TimelineChart({ data, mode }: Props) {
  if (data.length === 0) {
    return <div className="text-gray-500 text-center py-12">No timeline data available</div>;
  }

  const labels = [...new Set(data.map((d) => d.label))];

  if (mode === "attention") {
    const traces = labels.map((label) => {
      const points = data.filter((d) => d.label === label);
      return {
        x: points.map((p) => p.week_start),
        y: points.map((p) => p.share_of_attention),
        name: label,
        type: "scatter" as const,
        mode: "lines" as const,
        stackgroup: "one",
        groupnorm: "percent" as const,
      };
    });

    return (
      <Plot
        data={traces}
        layout={{
          yaxis: { title: { text: "Share of Attention (%)" }, ticksuffix: "%" },
          xaxis: { title: { text: "Week" } },
          legend: { orientation: "h", y: -0.2 },
          hovermode: "x unified",
          height: 500,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#d1d5db" },
          margin: { l: 60, r: 20, t: 20, b: 80 },
        }}
        config={{ responsive: true }}
        style={{ width: "100%" }}
      />
    );
  }

  // Z-Score mode
  const traces = labels.map((label) => {
    const points = data.filter((d) => d.label === label);
    return {
      x: points.map((p) => p.week_start),
      y: points.map((p) => p.z_score),
      name: label,
      type: "scatter" as const,
      mode: "lines+markers" as const,
    };
  });

  return (
    <Plot
      data={traces}
      layout={{
        yaxis: { title: { text: "Z-Score" } },
        xaxis: { title: { text: "Week" } },
        legend: { orientation: "h", y: -0.2 },
        hovermode: "x unified",
        height: 500,
        shapes: [
          { type: "rect", y0: 1.5, y1: 2.0, x0: 0, x1: 1, xref: "paper", fillcolor: "orange", opacity: 0.1, line: { width: 0 } },
          { type: "rect", y0: 2.0, y1: 4.0, x0: 0, x1: 1, xref: "paper", fillcolor: "red", opacity: 0.1, line: { width: 0 } },
          { type: "rect", y0: -2.0, y1: -1.5, x0: 0, x1: 1, xref: "paper", fillcolor: "orange", opacity: 0.1, line: { width: 0 } },
          { type: "rect", y0: -4.0, y1: -2.0, x0: 0, x1: 1, xref: "paper", fillcolor: "red", opacity: 0.1, line: { width: 0 } },
          { type: "line", y0: 0, y1: 0, x0: 0, x1: 1, xref: "paper", line: { color: "gray", dash: "dash" } },
        ],
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: "#d1d5db" },
        margin: { l: 60, r: 20, t: 20, b: 80 },
      }}
      config={{ responsive: true }}
      style={{ width: "100%" }}
    />
  );
}
