"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useRef, useEffect, useState, useMemo } from "react";
import { TimelinePoint, Cover, coverImageUrl } from "@/lib/api";
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

// Muted grey for the "Other" bucket — blends into background
const OTHER_COLOR_LIGHT = "#d4d0cc";
const OTHER_COLOR_DARK = "#44403c";

const THUMB_W = 34;
const THUMB_H = Math.round(THUMB_W * (66 / 51));
// Plotly margin matches sharedLayout below
const MARGIN_L = 50;
const MARGIN_R = 16;

interface Props {
  data: TimelinePoint[];
  mode: "attention" | "zscore";
  covers?: Cover[];
  colorMap?: Record<string, string>;
}

export default function TimelineChart({ data, mode, covers, colorMap }: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [containerW, setContainerW] = useState(0);
  const [hoveredCoverId, setHoveredCoverId] = useState<number | null>(null);
  const [zoomState, setZoomState] = useState<{ id: number; transform: string } | null>(null);
  const [loadedCovers, setLoadedCovers] = useState<Set<number>>(new Set());

  function handleThumbClick(cover: Cover, e: React.MouseEvent) {
    if (zoomState?.id === cover.id) {
      setZoomState(null);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const tx = window.innerWidth / 2 - cx;
    const ty = window.innerHeight / 2 - cy;
    setZoomState({ id: cover.id, transform: `translate(${tx}px, ${ty}px) scale(12)` });
  }

  // Observe container width for proportional cover placement
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerW(entry.contentRect.width);
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Theme-aware chart colors
  const textColor = isDark ? "#f5f0eb" : "#1a1a1a";
  const secondaryColor = isDark ? "#a8a29e" : "#666";
  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)";
  const zerolineColor = isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)";
  const lineColor = isDark ? "#44403c" : "#e8e5e1";
  const bandColor = isDark ? "rgba(239,68,68,0.06)" : "rgba(227,18,11,0.04)";
  const bandStrongColor = isDark ? "rgba(239,68,68,0.12)" : "rgba(227,18,11,0.08)";
  const thresholdColor = isDark ? "rgba(239,68,68,0.3)" : "rgba(227,18,11,0.2)";
  const coverLineColor = isDark ? "rgba(200,200,200,0.3)" : "rgba(100,100,100,0.3)";

  // In attention mode, keep "Other" (renders at bottom of stack for 100% sum)
  // In z-score mode, filter it out (z-score for an aggregated bucket is meaningless)
  const filtered = useMemo(
    () => data.filter((d) => mode === "attention" || d.label !== "Other"),
    [data, mode],
  );
  // Put "Other" first so it renders at the bottom of the stacked area
  const labels = useMemo(() => {
    const all = [...new Set(filtered.map((d) => d.label))];
    const otherIdx = all.indexOf("Other");
    if (otherIdx > 0) {
      all.splice(otherIdx, 1);
      all.unshift("Other");
    }
    return all;
  }, [filtered]);

  // Compute date range from the actual data
  const { minDate, dateSpan } = useMemo(() => {
    const allDates = filtered.map((d) => new Date(d.week_start).getTime());
    const min = Math.min(...allDates);
    const max = Math.max(...allDates);
    return { minDate: min, maxDate: max, dateSpan: max - min || 1 };
  }, [filtered]);

  // Compute cover thumbnail positions proportionally
  const plotWidth = containerW - MARGIN_L - MARGIN_R;
  const thumbPositions = useMemo(() => {
    if (!covers || covers.length === 0 || plotWidth <= 0) return [];
    return covers
      .map((cover) => {
        const t = new Date(cover.date).getTime();
        const frac = (t - minDate) / dateSpan;
        const left = MARGIN_L + frac * plotWidth;
        return { cover, left };
      })
      .filter(({ left }) => left >= MARGIN_L - THUMB_W / 2 && left <= MARGIN_L + plotWidth + THUMB_W / 2);
  }, [covers, plotWidth, minDate, dateSpan]);

  // Cover vertical line shapes
  const coverShapes: Partial<Plotly.Shape>[] = useMemo(() => {
    if (!covers?.length) return [];
    return covers.map((c) => ({
      type: "line" as const,
      x0: c.date,
      x1: c.date,
      y0: 0,
      y1: 1,
      yref: "paper" as const,
      line: { color: coverLineColor, dash: "dot" as const, width: 1 },
    }));
  }, [covers, coverLineColor]);

  const sharedLayout: Partial<Plotly.Layout> = useMemo(() => ({
    height: 380,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: {
      family: "'DM Sans', sans-serif",
      color: textColor,
      size: 11,
    },
    showlegend: false,
    hovermode: "closest" as const,
    hoverlabel: {
      bgcolor: isDark ? "#1c1917" : "#ffffff",
      bordercolor: isDark ? "#44403c" : "#e8e5e1",
      font: {
        color: isDark ? "#f5f0eb" : "#1a1a1a",
        family: "'DM Sans', sans-serif",
        size: 11,
      },
      namelength: -1,
    },
    margin: { l: MARGIN_L, r: MARGIN_R, t: 8, b: 36 },
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
  }), [isDark, textColor, secondaryColor, gridColor, lineColor]);

  const plotProps = {
    config: { responsive: true, displayModeBar: false } as Partial<Plotly.Config>,
    style: { width: "100%" },
  };

  const { traces, layout } = useMemo(() => {
    // Plotly's installed types omit the supported "points+fills" hover mode.
    let t: Plotly.Data[];
    let l: Partial<Plotly.Layout>;

    if (mode === "attention") {
      const uniqueWeeks = [...new Set(filtered.map((d) => d.week_start))];
      const useBars = uniqueWeeks.length <= 1;

      const otherColor = isDark ? OTHER_COLOR_DARK : OTHER_COLOR_LIGHT;
      t = labels.map((label, i) => {
        const points = filtered.filter((d) => d.label === label);
        const isOther = label === "Other";
        const color = isOther ? otherColor : (colorMap?.[label] ?? PALETTE[i % PALETTE.length]);
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
          line: { width: 0, shape: "spline" as const, smoothing: 1.3 },
          fillcolor: color + (isOther ? "88" : "cc"),
          hoveron: "points+fills" as unknown as Plotly.PlotData["hoveron"],
          hovertemplate: `%{fullData.name} %{y:.1f}%<extra></extra>`,
          hoverlabel: { bgcolor: isDark ? "#1c1917" : "#ffffff", font: { color: isDark ? "#f5f0eb" : "#1a1a1a" } },
        };
      });

      l = {
        ...sharedLayout,
        ...(!useBars ? { hovermode: "closest" as const } : {}),
        yaxis: {
          ...sharedLayout.yaxis,
          title: { text: "Share of Attention", font: { size: 11, color: secondaryColor } },
          ticksuffix: "%",
          range: [0, 100],
        },
        ...(useBars ? { barmode: "group" as const } : {}),
        shapes: [...coverShapes],
      };
    } else {
      // Z-Score mode
      const uniqueWeeksZ = [...new Set(filtered.map((d) => d.week_start))];
      const useBarsZ = uniqueWeeksZ.length <= 1;

      t = labels.map((label, i) => {
        const points = filtered.filter((d) => d.label === label);
        const color = colorMap?.[label] ?? PALETTE[i % PALETTE.length];
        if (useBarsZ) {
          return {
            x: [label],
            y: [points[0]?.z_score ?? 0],
            name: label,
            type: "bar" as const,
            marker: { color },
            hovertemplate: `<b>%{fullData.name}</b><br>z = %{y:.2f}<extra></extra>`,
          };
        }
        return {
          x: points.map((p) => p.week_start),
          y: points.map((p) => p.z_score),
          customdata: points.map((p) => p.share_of_attention),
          name: label,
          type: "scatter" as const,
          mode: "lines+markers" as const,
          line: { color, width: 2 },
          marker: { size: 4, color },
          hovertemplate: `<b>%{fullData.name}</b><br>z = %{y:.2f} · %{customdata:.1f}%<extra></extra>`,
        };
      });

      const zScoreShapes = useBarsZ ? [] : [
        { type: "rect" as const, y0: 1.5, y1: 2.0, x0: 0, x1: 1, xref: "paper" as const, fillcolor: bandColor, line: { width: 0 } },
        { type: "rect" as const, y0: 2.0, y1: 4.0, x0: 0, x1: 1, xref: "paper" as const, fillcolor: bandStrongColor, line: { width: 0 } },
        { type: "rect" as const, y0: -2.0, y1: -1.5, x0: 0, x1: 1, xref: "paper" as const, fillcolor: bandColor, line: { width: 0 } },
        { type: "rect" as const, y0: -4.0, y1: -2.0, x0: 0, x1: 1, xref: "paper" as const, fillcolor: bandStrongColor, line: { width: 0 } },
        { type: "line" as const, y0: 2.0, y1: 2.0, x0: 0, x1: 1, xref: "paper" as const, line: { color: thresholdColor, dash: "dot" as const, width: 1 } },
        { type: "line" as const, y0: -2.0, y1: -2.0, x0: 0, x1: 1, xref: "paper" as const, line: { color: thresholdColor, dash: "dot" as const, width: 1 } },
      ];

      l = {
        ...sharedLayout,
        ...(useBarsZ ? { barmode: "group" as const } : {}),
        yaxis: {
          ...sharedLayout.yaxis,
          title: { text: "Z-Score", font: { size: 11, color: secondaryColor } },
          zeroline: true,
          zerolinecolor: zerolineColor,
        },
        shapes: [...zScoreShapes, ...coverShapes],
      };
    }

    return { traces: t, layout: l };
  }, [filtered, labels, mode, isDark, colorMap, coverShapes, sharedLayout, secondaryColor, bandColor, bandStrongColor, thresholdColor, zerolineColor]);

  return (
    <div ref={wrapperRef} style={{ position: "relative" }}>
      {data.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: "3rem 1rem",
          color: "var(--text-secondary)",
          fontSize: "0.85rem",
          fontFamily: "var(--font-sans)",
        }}>
          No timeline data available. Run the pipeline to discover narratives.
        </div>
      ) : (
        <>
          {/* Cover thumbnail strip — always reserve space when covers exist to prevent layout shift */}
          {covers && covers.length > 0 && (
            <div style={{ position: "relative", height: 50, marginBottom: -4, pointerEvents: "none" }}>
              {thumbPositions.map(({ cover, left }) => {
                const isZoomed = zoomState?.id === cover.id;
                const isHovered = hoveredCoverId === cover.id && !isZoomed;
                const showLabel = isHovered || isZoomed;
                return (
                  <div
                    key={cover.id}
                    onMouseEnter={() => setHoveredCoverId(cover.id)}
                    onMouseLeave={() => setHoveredCoverId(null)}
                    onClick={(e) => handleThumbClick(cover, e)}
                    style={{
                      position: "absolute",
                      top: 4,
                      left: left - THUMB_W / 2,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      pointerEvents: "auto",
                      zIndex: isZoomed ? 1000 : isHovered ? 100 : 10,
                      transform: isZoomed ? zoomState.transform : "none",
                      transition: "transform 0.25s ease",
                      cursor: "pointer",
                    }}
                  >
                    <Image
                      src={coverImageUrl(cover.image_url, true)}
                      alt={`Economist ${cover.date}`}
                      width={THUMB_W}
                      height={THUMB_H}
                      loading="lazy"
                      unoptimized
                      onLoad={() => setLoadedCovers(prev => { const next = new Set(prev); next.add(cover.id); return next; })}
                      style={{
                        display: "block",
                        borderRadius: 2,
                        border: `1px solid ${isHovered || isZoomed ? "var(--red)" : "var(--border)"}`,
                        objectFit: "cover",
                        opacity: loadedCovers.has(cover.id) ? 1 : 0,
                        transition: "opacity 0.15s ease, transform 0.2s ease, box-shadow 0.2s ease",
                        transform: isHovered ? "scale(4)" : "none",
                        transformOrigin: "top center",
                        boxShadow: isZoomed
                          ? "0 8px 40px rgba(0,0,0,0.5)"
                          : isHovered
                            ? "0 4px 20px rgba(0,0,0,0.3)"
                            : "none",
                      }}
                    />
                    <span
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontSize: showLabel ? "0.6rem" : 0,
                        color: "var(--text-secondary)",
                        whiteSpace: "nowrap",
                        opacity: showLabel ? 1 : 0,
                        transition: "opacity 0.15s ease, font-size 0.15s ease",
                        pointerEvents: "none",
                        marginTop: 2,
                      }}
                    >
                      {new Date(cover.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          {zoomState !== null && (
            <div
              onClick={() => setZoomState(null)}
              style={{
                position: "fixed",
                inset: 0,
                zIndex: 999,
                background: "rgba(0, 0, 0, 0.7)",
                cursor: "pointer",
                animation: "fadeIn 0.2s ease",
              }}
            />
          )}
          <Plot data={traces} layout={layout} {...plotProps} />
        </>
      )}
    </div>
  );
}
