"use client";

import dynamic from "next/dynamic";
import { TimelinePoint } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

// Warm, editorial palette — muted but distinct
const PALETTE = [
  "#E3120B", // red (brand)
  "#1a6b8a", // teal
  "#c4841d", // amber
  "#5b7553", // sage
  "#7b5ea7", // plum
  "#d45d79", // rose
  "#3d85c6", // steel blue
  "#8c6d46", // warm brown
  "#6b8e9b", // slate
  "#b85c38", // rust
  "#4a8c7f", // jade
  "#9b6b9e", // mauve
];

interface Props {
  data: TimelinePoint[];
  mode: "attention" | "zscore";
}

export default function TimelineChart({ data, mode }: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  if (data.length === 0) {
    return (
      <div style={{
        textAlign: "center",
        padding: "3rem 1rem",
        color: "var(--text-secondary)",
        fontSize: "0.85rem",
        fontFamily: "var(--font-sans)",
      }}>
        No timeline data available. Run the pipeline to discover narratives.
      </div>
    );
  }

  // Theme-aware chart colors
  const textColor = isDark ? "#f5f0eb" : "#1a1a1a";
  const secondaryColor = isDark ? "#a8a29e" : "#999";
  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)";
  const zerolineColor = isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)";
  const lineColor = isDark ? "#44403c" : "#e8e5e1";
  const bandColor = isDark ? "rgba(239,68,68,0.06)" : "rgba(227,18,11,0.04)";
  const bandStrongColor = isDark ? "rgba(239,68,68,0.12)" : "rgba(227,18,11,0.08)";
  const thresholdColor = isDark ? "rgba(239,68,68,0.3)" : "rgba(227,18,11,0.2)";

  // Filter out "Other" bucket — only show real narratives
  const filtered = data.filter((d) => d.label !== "Other");
  const labels = [...new Set(filtered.map((d) => d.label))];

  const sharedLayout: Partial<Plotly.Layout> = {
    height: 380,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: {
      family: "'DM Sans', sans-serif",
      color: textColor,
      size: 11,
    },
    legend: {
      orientation: "h" as const,
      y: -0.25,
      font: { size: 10, color: secondaryColor },
    },
    hovermode: "x unified" as const,
    hoverlabel: {
      bgcolor: isDark ? "#292524" : "#ffffff",
      bordercolor: isDark ? "#44403c" : "#e8e5e1",
      font: {
        color: isDark ? "#f5f0eb" : "#1a1a1a",
        family: "'DM Sans', sans-serif",
        size: 11,
      },
    },
    margin: { l: 50, r: 16, t: 8, b: 70 },
    xaxis: {
      type: "date" as const,
      gridcolor: gridColor,
      linecolor: lineColor,
      tickfont: { size: 10, color: secondaryColor },
    },
    yaxis: {
      gridcolor: gridColor,
      linecolor: lineColor,
      tickfont: { size: 10, color: secondaryColor },
      zeroline: false,
    },
  };

  if (mode === "attention") {
    const uniqueWeeks = [...new Set(filtered.map((d) => d.week_start))];
    const useBars = uniqueWeeks.length <= 1;

    const traces = labels.map((label, i) => {
      const points = filtered.filter((d) => d.label === label);
      const color = PALETTE[i % PALETTE.length];
      if (useBars) {
        return {
          x: [label],
          y: [points[0]?.share_of_attention ?? 0],
          name: label,
          type: "bar" as const,
          marker: { color: color + "cc" },
          hovertemplate: `<b>%{fullData.name}</b><br>%{y:.1f}%<extra></extra>`,
        };
      }
      return {
        x: points.map((p) => p.week_start),
        y: points.map((p) => p.share_of_attention),
        name: label,
        type: "scatter" as const,
        mode: "lines" as const,
        stackgroup: "one",
        groupnorm: "percent" as const,
        line: { width: 0, shape: "spline" as const, smoothing: 1.3 },
        fillcolor: color + "cc",
        hovertemplate: `<b>%{fullData.name}</b><br>%{y:.1f}%<extra></extra>`,
      };
    });

    return (
      <Plot
        data={traces}
        layout={{
          ...sharedLayout,
          yaxis: {
            ...sharedLayout.yaxis,
            title: { text: "Share of Attention", font: { size: 11, color: secondaryColor } },
            ticksuffix: "%",
          },
          ...(useBars ? { barmode: "group" as const } : {}),
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    );
  }

  // Z-Score mode
  const uniqueWeeksZ = [...new Set(filtered.map((d) => d.week_start))];
  const useBarsZ = uniqueWeeksZ.length <= 1;

  const traces = labels.map((label, i) => {
    const points = filtered.filter((d) => d.label === label);
    if (useBarsZ) {
      return {
        x: [label],
        y: [points[0]?.z_score ?? 0],
        name: label,
        type: "bar" as const,
        marker: { color: PALETTE[i % PALETTE.length] },
        hovertemplate: `<b>%{fullData.name}</b><br>z = %{y:.2f}<extra></extra>`,
      };
    }
    return {
      x: points.map((p) => p.week_start),
      y: points.map((p) => p.z_score),
      name: label,
      type: "scatter" as const,
      mode: "lines+markers" as const,
      line: { color: PALETTE[i % PALETTE.length], width: 2 },
      marker: { size: 4, color: PALETTE[i % PALETTE.length] },
      hovertemplate: `<b>%{fullData.name}</b><br>z = %{y:.2f}<extra></extra>`,
    };
  });

  return (
    <Plot
      data={traces}
      layout={{
        ...sharedLayout,
        ...(useBarsZ ? { barmode: "group" as const } : {}),
          yaxis: {
            ...sharedLayout.yaxis,
            title: { text: "Z-Score", font: { size: 11, color: secondaryColor } },
            zeroline: true,
            zerolinecolor: zerolineColor,
          },
          shapes: useBarsZ ? [] : [
            // Alert bands
            { type: "rect", y0: 1.5, y1: 2.0, x0: 0, x1: 1, xref: "paper", fillcolor: bandColor, line: { width: 0 } },
            { type: "rect", y0: 2.0, y1: 4.0, x0: 0, x1: 1, xref: "paper", fillcolor: bandStrongColor, line: { width: 0 } },
            { type: "rect", y0: -2.0, y1: -1.5, x0: 0, x1: 1, xref: "paper", fillcolor: bandColor, line: { width: 0 } },
            { type: "rect", y0: -4.0, y1: -2.0, x0: 0, x1: 1, xref: "paper", fillcolor: bandStrongColor, line: { width: 0 } },
            // Threshold lines
            { type: "line", y0: 2.0, y1: 2.0, x0: 0, x1: 1, xref: "paper", line: { color: thresholdColor, dash: "dot", width: 1 } },
            { type: "line", y0: -2.0, y1: -2.0, x0: 0, x1: 1, xref: "paper", line: { color: thresholdColor, dash: "dot", width: 1 } },
          ],
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
  );
}
