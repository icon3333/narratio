"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchArticles, Article, ArticlesResponse } from "@/lib/api";

export default function ArticlesTab() {
  const [data, setData] = useState<ArticlesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchArticles({
        page,
        per_page: 50,
        source: source || undefined,
        search: search || undefined,
      });
      setData(res);
      // Collect unique sources from first load
      if (sources.length === 0 && res.articles.length > 0) {
        const unique = [...new Set(res.articles.map((a) => a.source).filter(Boolean))].sort();
        if (unique.length > 0) setSources(unique);
      }
    } catch {
      setError("Failed to load articles.");
    }
    setLoading(false);
  }, [page, search, source]);

  useEffect(() => {
    load();
  }, [load]);

  // Also fetch sources from a broader query on mount
  useEffect(() => {
    fetchArticles({ page: 1, per_page: 1 }).then(() => {
      // Get a large sample to discover sources
      fetchArticles({ page: 1, per_page: 200 }).then((res) => {
        const unique = [...new Set(res.articles.map((a) => a.source).filter(Boolean))].sort();
        if (unique.length > 0) setSources(unique);
      }).catch(() => {});
    }).catch(() => {});
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div className="fade-up" style={{ animationDelay: "0.08s" }}>
      <div
        style={{
          background: "var(--bg-card)",
          borderRadius: 3,
          boxShadow: "var(--card-shadow)",
          padding: "1.5rem",
        }}
      >
        <h2
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.05rem",
            fontWeight: 400,
            marginBottom: "1rem",
            color: "var(--text-primary)",
          }}
        >
          Articles
        </h2>

        <form onSubmit={handleSearch} className="articles-filter-bar">
          <input
            type="text"
            placeholder="Search headlines..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Sources</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="btn-pipeline"
            style={{
              display: "flex",
              alignItems: "center",
              background: "none",
              border: "1.5px solid var(--border)",
              borderRadius: 6,
              padding: "0.45rem 0.85rem",
              fontFamily: "var(--font-sans)",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
              letterSpacing: "0.03em",
            }}
          >
            Search
          </button>
        </form>

        {error && (
          <div
            style={{
              padding: "0.75rem 1rem",
              background: "var(--bg-error)",
              border: "1px solid var(--border-error)",
              borderRadius: 3,
              fontSize: "0.8rem",
              color: "var(--text-error)",
              marginBottom: "1rem",
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ padding: "1rem 0" }}>
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="skeleton"
                style={{ height: 40, width: "100%", marginBottom: 6, animationDelay: `${i * 0.05}s` }}
              />
            ))}
          </div>
        ) : data && data.articles.length > 0 ? (
          <>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <Th align="left">Headline</Th>
                    <Th align="left">Source</Th>
                    <Th align="left">Published</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.articles.map((a, i) => (
                    <tr
                      key={i}
                      className="narrative-row"
                      style={{ borderBottom: "1px solid var(--border-subtle)" }}
                    >
                      <Td align="left">
                        {a.url ? (
                          <a
                            href={a.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="link-hover"
                            style={{
                              color: "var(--text-primary)",
                              textDecoration: "none",
                              fontWeight: 500,
                            }}
                          >
                            {a.headline}
                          </a>
                        ) : (
                          a.headline
                        )}
                      </Td>
                      <Td align="left" style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {a.source}
                      </Td>
                      <Td align="left" style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {formatDate(a.published_at)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Prev
                </button>
                <span>
                  Page {page} of {totalPages}
                </span>
                <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div
            style={{
              textAlign: "center",
              padding: "2rem 1rem",
              color: "var(--text-secondary)",
              fontSize: "0.85rem",
            }}
          >
            No articles found.
          </div>
        )}
      </div>
    </div>
  );
}

function Th({ children, align }: { children: React.ReactNode; align: "left" | "right" }) {
  return (
    <th
      style={{
        textAlign: align,
        padding: "0.6rem 0.75rem",
        fontWeight: 500,
        fontSize: "0.7rem",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "var(--text-secondary)",
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align,
  style,
}: {
  children: React.ReactNode;
  align: "left" | "right";
  style?: React.CSSProperties;
}) {
  return (
    <td style={{ textAlign: align, padding: "0.65rem 0.75rem", ...style }}>{children}</td>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr.includes("T") ? dateStr : dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
