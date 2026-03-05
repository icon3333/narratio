"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchMapData, fetchDateRange, MapCountry, DateRange } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type FilterMode = "all" | "year" | "month" | "custom";

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "none",
        border: active ? "1.5px solid var(--red)" : "1.5px solid var(--border)",
        borderRadius: 6,
        padding: "0.4rem 0.7rem",
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

export default function MapTab() {
  const { theme } = useTheme();
  const [data, setData] = useState<MapCountry[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  // Derive available years from date range
  const years = useMemo(() => {
    if (!dateRange?.min_date || !dateRange?.max_date) return [];
    const minYear = new Date(dateRange.min_date).getFullYear();
    const maxYear = new Date(dateRange.max_date).getFullYear();
    const result: number[] = [];
    for (let y = maxYear; y >= minYear; y--) result.push(y);
    return result;
  }, [dateRange]);

  // Compute API params from filter state
  const filterParams = useMemo(() => {
    if (filterMode === "all") return {};
    if (filterMode === "custom" && customStart && customEnd) {
      return { start: customStart + "-01", end: customEnd + "-31" };
    }
    if (filterMode === "year" && selectedYear) {
      return { start: `${selectedYear}-01-01`, end: `${selectedYear}-12-31` };
    }
    if (filterMode === "month" && selectedYear && selectedMonth) {
      const m = String(selectedMonth).padStart(2, "0");
      return { start: `${selectedYear}-${m}-01`, end: `${selectedYear}-${m}-31` };
    }
    return {};
  }, [filterMode, selectedYear, selectedMonth, customStart, customEnd]);

  // Fetch date range on mount
  useEffect(() => {
    fetchDateRange().then(setDateRange).catch(() => {});
  }, []);

  // Fetch map data when filters change
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchMapData(filterParams);
      setData(result);
    } catch {
      setError("Failed to load map data. Is the API running?");
    }
    setLoading(false);
  }, [filterParams]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleYearClick = (year: number) => {
    if (selectedYear === year && filterMode === "year") {
      // Deselect
      setFilterMode("all");
      setSelectedYear(null);
      setSelectedMonth(null);
    } else {
      setSelectedYear(year);
      setSelectedMonth(null);
      setFilterMode("year");
      setShowCustom(false);
    }
  };

  const handleMonthClick = (month: number) => {
    if (selectedMonth === month) {
      // Deselect month, go back to year
      setSelectedMonth(null);
      setFilterMode("year");
    } else {
      setSelectedMonth(month);
      setFilterMode("month");
    }
  };

  const handleAllClick = () => {
    setFilterMode("all");
    setSelectedYear(null);
    setSelectedMonth(null);
    setShowCustom(false);
  };

  const handleCustomApply = () => {
    if (customStart && customEnd) {
      setFilterMode("custom");
      setSelectedYear(null);
      setSelectedMonth(null);
    }
  };

  // Read CSS vars for theming
  const cssVarRef = useRef<{ red: string; bg: string; land: string; border: string; text: string }>({
    red: "#E3120B", bg: "#ffffff", land: "#f5f0eb", border: "#d4d0cc", text: "#1a1a1a",
  });
  useEffect(() => {
    const s = getComputedStyle(document.documentElement);
    cssVarRef.current = {
      red: s.getPropertyValue("--red").trim() || "#E3120B",
      bg: s.getPropertyValue("--bg-page").trim() || "#ffffff",
      land: s.getPropertyValue("--bg-card").trim() || "#f5f0eb",
      border: s.getPropertyValue("--border").trim() || "#d4d0cc",
      text: s.getPropertyValue("--text-primary").trim() || "#1a1a1a",
    };
  }, [theme]);

  const isDark = theme === "dark";

  // Build Plotly data
  const plotData = useMemo(() => {
    if (data.length === 0) return [];

    // Filter out non-ISO codes (EUR, OPEC, NATO, etc.) — Plotly only maps ISO alpha-3
    const isoData = data.filter((d) => d.country_code.length === 3 && !["EUR", "IMF", "WBG"].includes(d.country_code));
    // Also include OPEC/NATO entries but they won't render on map

    const locations = isoData.map((d) => d.country_code);
    const z = isoData.map((d) => d.article_count);
    const text = isoData.map((d) => {
      const narrs = d.top_narratives
        .slice(0, 3)
        .map((n) => `  ${n.label} (${n.count})`)
        .join("<br>");
      return `<b>${d.country_name}</b><br>` +
        `Articles: ${d.article_count} (${d.share}%)<br>` +
        (narrs ? `<br>Top narratives:<br>${narrs}` : "");
    });

    const { red } = cssVarRef.current;
    // Parse hex to RGB for gradient
    const r = parseInt(red.slice(1, 3), 16);
    const g = parseInt(red.slice(3, 5), 16);
    const b = parseInt(red.slice(5, 7), 16);

    return [{
      type: "choropleth" as const,
      locationmode: "ISO-3" as const,
      locations,
      z,
      text,
      hoverinfo: "text" as const,
      colorscale: [
        [0, isDark ? `rgba(${r},${g},${b},0.05)` : `rgba(${r},${g},${b},0.04)`],
        [0.2, `rgba(${r},${g},${b},0.15)`],
        [0.5, `rgba(${r},${g},${b},0.35)`],
        [0.8, `rgba(${r},${g},${b},0.6)`],
        [1, `rgba(${r},${g},${b},0.85)`],
      ],
      showscale: true,
      colorbar: {
        title: { text: "Articles", font: { family: "var(--font-sans)", size: 11, color: cssVarRef.current.text } },
        tickfont: { family: "var(--font-sans)", size: 10, color: cssVarRef.current.text },
        thickness: 12,
        len: 0.5,
        bgcolor: "transparent",
        outlinewidth: 0,
      },
      marker: {
        line: {
          color: cssVarRef.current.border,
          width: 0.5,
        },
      },
    }];
  }, [data, isDark, theme]);

  const plotLayout = useMemo(() => ({
    geo: {
      showframe: false,
      showcoastlines: true,
      coastlinecolor: cssVarRef.current.border,
      projection: { type: "natural earth" as const },
      bgcolor: "transparent",
      landcolor: isDark ? "#2a2725" : "#f8f5f1",
      oceancolor: isDark ? "#1a1816" : "#f0ede8",
      showocean: true,
      showland: true,
      showcountries: true,
      countrycolor: cssVarRef.current.border,
      countrywidth: 0.3,
      lonaxis: { range: [-160, 170] },
      lataxis: { range: [-55, 75] },
    },
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    dragmode: false as const,
    height: 480,
  }), [isDark, theme]);

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Non-ISO entries (supranational) to show as a separate list below the map
  const supranational = useMemo(
    () => data.filter((d) => ["EUR", "OPEC", "NATO", "IMF", "WBG"].includes(d.country_code)),
    [data],
  );

  if (error) {
    return (
      <div className="fade-up" style={{ padding: "2rem", textAlign: "center" }}>
        <p style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>{error}</p>
      </div>
    );
  }

  return (
    <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Time Filter Bar */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.4rem",
          alignItems: "center",
        }}
      >
        <ModeButton active={filterMode === "all"} onClick={handleAllClick}>All</ModeButton>
        {years.map((y) => (
          <ModeButton
            key={y}
            active={selectedYear === y && (filterMode === "year" || filterMode === "month")}
            onClick={() => handleYearClick(y)}
          >
            {y}
          </ModeButton>
        ))}
        <ModeButton
          active={showCustom}
          onClick={() => { setShowCustom((v) => !v); if (showCustom) { setFilterMode(selectedYear ? "year" : "all"); } }}
        >
          Custom
        </ModeButton>
      </div>

      {/* Month chips (when year selected) */}
      {selectedYear && (filterMode === "year" || filterMode === "month") && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
          {months.map((m, i) => (
            <ModeButton
              key={i}
              active={selectedMonth === i + 1}
              onClick={() => handleMonthClick(i + 1)}
            >
              {m}
            </ModeButton>
          ))}
        </div>
      )}

      {/* Custom date range */}
      {showCustom && (
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="month"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.75rem",
              padding: "0.35rem 0.5rem",
              border: "1.5px solid var(--border)",
              borderRadius: 6,
              background: "var(--bg-card)",
              color: "var(--text-primary)",
            }}
          />
          <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>to</span>
          <input
            type="month"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.75rem",
              padding: "0.35rem 0.5rem",
              border: "1.5px solid var(--border)",
              borderRadius: 6,
              background: "var(--bg-card)",
              color: "var(--text-primary)",
            }}
          />
          <ModeButton active={false} onClick={handleCustomApply}>Apply</ModeButton>
        </div>
      )}

      {/* Map Card */}
      <div
        style={{
          background: "var(--bg-card)",
          borderRadius: 3,
          boxShadow: "var(--card-shadow)",
          overflow: "hidden",
          padding: "1.5rem",
        }}
      >
        <h2 style={{
          fontFamily: "var(--font-serif)",
          fontSize: "1.05rem",
          fontWeight: 400,
          marginBottom: "1rem",
          color: "var(--text-primary)",
        }}>
          News Geography
        </h2>

        {loading ? (
          <div>
            <div className="skeleton" style={{ height: 480, width: "100%" }} />
          </div>
        ) : data.length === 0 ? (
          <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <p style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
              No country data available. Run the pipeline to extract country mentions.
            </p>
          </div>
        ) : (
          <Plot
            data={plotData as Plotly.Data[]}
            layout={plotLayout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        )}
      </div>

      {/* Supranational entities (shown below map if present) */}
      {supranational.length > 0 && !loading && (
        <div
          style={{
            background: "var(--bg-card)",
            borderRadius: 3,
            boxShadow: "var(--card-shadow)",
            padding: "1.5rem",
          }}
        >
          <h3 style={{
            fontFamily: "var(--font-serif)",
            fontSize: "0.95rem",
            fontWeight: 400,
            marginBottom: "0.75rem",
            color: "var(--text-primary)",
          }}>
            Supranational & Organizations
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
            {supranational.map((d) => (
              <div key={d.country_code} style={{
                padding: "0.5rem 0.75rem",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontFamily: "var(--font-sans)",
                fontSize: "0.78rem",
              }}>
                <div style={{ fontWeight: 500, color: "var(--text-primary)", marginBottom: "0.2rem" }}>
                  {d.country_name}
                </div>
                <div style={{ color: "var(--text-secondary)" }}>
                  {d.article_count} articles ({d.share}%)
                </div>
                {d.top_narratives.length > 0 && (
                  <div style={{ marginTop: "0.3rem", fontSize: "0.72rem", color: "var(--text-secondary)" }}>
                    {d.top_narratives.map((n) => n.label).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
