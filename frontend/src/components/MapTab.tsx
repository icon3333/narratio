"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchMapData, fetchDateRange, MapCountry, DateRange } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type FilterMode = "all" | "year" | "month" | "custom";

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function MonthPicker({
  value,
  onChange,
  minDate,
  maxDate,
  label,
}: {
  value: string; // "YYYY-MM" or ""
  onChange: (v: string) => void;
  minDate: string | null;
  maxDate: string | null;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Parse bounds
  const minYM = minDate ? { y: new Date(minDate).getFullYear(), m: new Date(minDate).getMonth() + 1 } : null;
  const maxYM = maxDate ? { y: new Date(maxDate).getFullYear(), m: new Date(maxDate).getMonth() + 1 } : null;

  // Current display year for the grid
  const parsedYear = value ? parseInt(value.slice(0, 4)) : (maxYM?.y ?? new Date().getFullYear());
  const [displayYear, setDisplayYear] = useState(parsedYear);

  // Sync display year when value changes
  useEffect(() => {
    if (value) setDisplayYear(parseInt(value.slice(0, 4)));
  }, [value]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const canGoBack = minYM ? displayYear > minYM.y : true;
  const canGoForward = maxYM ? displayYear < maxYM.y : true;

  const isInRange = (month: number) => {
    if (minYM && (displayYear < minYM.y || (displayYear === minYM.y && month < minYM.m))) return false;
    if (maxYM && (displayYear > maxYM.y || (displayYear === maxYM.y && month > maxYM.m))) return false;
    return true;
  };

  const selectedMonth = value ? parseInt(value.slice(5, 7)) : null;
  const selectedYear = value ? parseInt(value.slice(0, 4)) : null;

  const displayValue = value
    ? `${MONTH_LABELS[parseInt(value.slice(5, 7)) - 1]} ${value.slice(0, 4)}`
    : label;

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.75rem",
          padding: "0.35rem 0.6rem",
          border: "1.5px solid var(--border)",
          borderRadius: 6,
          background: "var(--bg-card)",
          color: value ? "var(--text-primary)" : "var(--text-secondary)",
          cursor: "pointer",
          minWidth: 90,
          textAlign: "left",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.4rem",
        }}
      >
        {displayValue}
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d={open ? "M2 6L5 3L8 6" : "M2 4L5 7L8 4"} />
        </svg>
      </button>
      {open && (
        <div style={{
          position: "absolute",
          top: "calc(100% + 4px)",
          left: 0,
          zIndex: 100,
          background: "var(--bg-card)",
          border: "1.5px solid var(--border)",
          borderRadius: 8,
          boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          padding: "0.6rem",
          width: 220,
        }}>
          {/* Year nav */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <button
              onClick={() => canGoBack && setDisplayYear((y) => y - 1)}
              disabled={!canGoBack}
              style={{
                background: "none", border: "none", cursor: canGoBack ? "pointer" : "default",
                color: canGoBack ? "var(--text-primary)" : "var(--border)",
                fontSize: "0.85rem", padding: "0.15rem 0.4rem", borderRadius: 4,
              }}
            >
              &lsaquo;
            </button>
            <span style={{
              fontFamily: "var(--font-sans)", fontSize: "0.8rem", fontWeight: 600,
              color: "var(--text-primary)",
            }}>
              {displayYear}
            </span>
            <button
              onClick={() => canGoForward && setDisplayYear((y) => y + 1)}
              disabled={!canGoForward}
              style={{
                background: "none", border: "none", cursor: canGoForward ? "pointer" : "default",
                color: canGoForward ? "var(--text-primary)" : "var(--border)",
                fontSize: "0.85rem", padding: "0.15rem 0.4rem", borderRadius: 4,
              }}
            >
              &rsaquo;
            </button>
          </div>
          {/* Month grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "3px" }}>
            {MONTH_LABELS.map((ml, i) => {
              const m = i + 1;
              const inRange = isInRange(m);
              const isSelected = selectedYear === displayYear && selectedMonth === m;
              return (
                <button
                  key={m}
                  disabled={!inRange}
                  onClick={() => {
                    if (!inRange) return;
                    const val = `${displayYear}-${String(m).padStart(2, "0")}`;
                    onChange(val);
                    setOpen(false);
                  }}
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: "0.7rem",
                    padding: "0.35rem 0",
                    border: isSelected ? "1.5px solid var(--red)" : "1px solid transparent",
                    borderRadius: 5,
                    background: isSelected ? "var(--red)" : "transparent",
                    color: isSelected
                      ? "#fff"
                      : inRange
                        ? "var(--text-primary)"
                        : "var(--border)",
                    cursor: inRange ? "pointer" : "default",
                    fontWeight: isSelected ? 600 : 400,
                    transition: "all 0.1s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (inRange && !isSelected) {
                      e.currentTarget.style.background = "var(--bg-page)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = "transparent";
                    }
                  }}
                >
                  {ml}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

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
  const hasLoaded = useRef(false);
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
    fetchDateRange().then(setDateRange).catch((err) => console.error("Failed to fetch date range:", err));
  }, []);

  // Fetch map data when filters change
  const loadData = useCallback(async () => {
    if (!hasLoaded.current) setLoading(true);
    setError(null);
    try {
      const result = await fetchMapData(filterParams);
      setData(result);
      hasLoaded.current = true;
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
        [0, isDark ? `rgba(${r},${g},${b},0.15)` : `rgba(${r},${g},${b},0.1)`],
        [0.2, isDark ? `rgba(${r},${g},${b},0.35)` : `rgba(${r},${g},${b},0.25)`],
        [0.5, `rgba(${r},${g},${b},0.5)`],
        [0.8, `rgba(${r},${g},${b},0.7)`],
        [1, `rgba(${r},${g},${b},0.92)`],
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
          color: isDark ? "rgba(10,10,10,0.8)" : "rgba(120,120,120,0.3)",
          width: 0.3,
        },
      },
    }];
  }, [data, isDark, theme]);

  const plotLayout = useMemo(() => ({
    geo: {
      showframe: false,
      showcoastlines: true,
      coastlinecolor: isDark ? "rgba(160,160,160,0.2)" : "rgba(100,100,100,0.2)",
      coastlinewidth: 0.3,
      projection: { type: "natural earth" as const },
      bgcolor: "transparent",
      landcolor: isDark ? "#1c1c1c" : "#f5f5f4",
      oceancolor: isDark ? "#0a0a0a" : "#e5e5e5",
      showocean: true,
      showland: true,
      showcountries: true,
      countrycolor: isDark ? "rgba(10,10,10,0.8)" : "rgba(120,120,120,0.25)",
      countrywidth: 0.2,
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
          onClick={() => {
            if (showCustom) {
              setShowCustom(false);
              setFilterMode(selectedYear ? "year" : "all");
            } else {
              setShowCustom(true);
              setSelectedYear(null);
              setSelectedMonth(null);
              if (filterMode !== "custom") setFilterMode("all");
            }
          }}
        >
          Custom
        </ModeButton>
      </div>

      {/* Month slider (when year selected) */}
      {selectedYear && (filterMode === "year" || filterMode === "month") && (() => {
        const minM = dateRange?.min_date && new Date(dateRange.min_date).getFullYear() === selectedYear
          ? new Date(dateRange.min_date).getMonth() + 1 : 1;
        const maxM = dateRange?.max_date && new Date(dateRange.max_date).getFullYear() === selectedYear
          ? new Date(dateRange.max_date).getMonth() + 1 : 12;
        return (
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0 0.25rem" }}>
            <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--text-secondary)", minWidth: "2rem" }}>
              {selectedMonth ? months[selectedMonth - 1] : "All"}
            </span>
            <input
              type="range"
              min={0}
              max={maxM}
              value={selectedMonth ?? 0}
              onChange={(e) => {
                let v = parseInt(e.target.value);
                if (v !== 0 && v < minM) v = minM;
                if (v === 0) { setSelectedMonth(null); setFilterMode("year"); }
                else handleMonthClick(v);
              }}
              style={{
                flex: 1,
                accentColor: "var(--text-secondary)",
                cursor: "pointer",
                height: "2px",
              }}
            />
            <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--text-secondary)", minWidth: "2rem", textAlign: "right" }}>
              {months[maxM - 1]}
            </span>
          </div>
        );
      })()}

      {/* Custom date range */}
      {showCustom && (
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <MonthPicker
            value={customStart}
            onChange={setCustomStart}
            minDate={dateRange?.min_date ?? null}
            maxDate={customEnd ? customEnd + "-28" : (dateRange?.max_date ?? null)}
            label="From"
          />
          <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>to</span>
          <MonthPicker
            value={customEnd}
            onChange={setCustomEnd}
            minDate={customStart ? customStart + "-01" : (dateRange?.min_date ?? null)}
            maxDate={dateRange?.max_date ?? null}
            label="To"
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
