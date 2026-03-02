"use client";

import { useState } from "react";
import Link from "next/link";
import { Narrative } from "@/lib/api";

interface Props {
  narratives: Narrative[];
  topIds?: Set<number>;
}

export default function NarrativeTable({ narratives, topIds }: Props) {
  const [showOther, setShowOther] = useState(false);

  if (narratives.length === 0) {
    return (
      <div style={{
        textAlign: "center",
        padding: "2rem 1rem",
        color: "var(--text-secondary)",
        fontSize: "0.85rem",
      }}>
        No narratives discovered yet. Run the pipeline to get started.
      </div>
    );
  }

  const featured = topIds ? narratives.filter((n) => topIds.has(n.id)) : narratives;
  const other = topIds ? narratives.filter((n) => !topIds.has(n.id)) : [];

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            <Th align="left" width={40}>#</Th>
            <Th align="left">Narrative</Th>
            <Th align="right">Articles</Th>
            <Th align="left">First Seen</Th>
            <Th align="left">Last Seen</Th>
            <Th align="left">Status</Th>
          </tr>
        </thead>
        <tbody>
          {featured.map((n, i) => (
            <NarrativeRow key={n.id} narrative={n} index={i + 1} />
          ))}
        </tbody>
      </table>

      {other.length > 0 && (
        <>
          <button
            className="btn-show-other"
            onClick={() => setShowOther(!showOther)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              width: "100%",
              background: "none",
              border: "none",
              borderTop: "1px solid var(--border)",
              padding: "0.7rem 0.75rem",
              fontFamily: "var(--font-sans)",
              fontSize: "0.75rem",
              fontWeight: 500,
              color: "var(--text-secondary)",
              cursor: "pointer",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              style={{
                transform: showOther ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform 0.2s ease",
              }}
            >
              <path d="M3 1 L7 5 L3 9" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            {other.length} other narrative{other.length !== 1 ? "s" : ""}
          </button>

          {showOther && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <tbody>
                {other.map((n, i) => (
                  <NarrativeRow key={n.id} narrative={n} index={featured.length + i + 1} dimmed />
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}

function NarrativeRow({ narrative: n, index, dimmed }: { narrative: Narrative; index: number; dimmed?: boolean }) {
  return (
    <tr
      className="narrative-row"
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        opacity: dimmed ? 0.55 : 1,
      }}
    >
      <Td align="left" style={{ color: "var(--text-secondary)", fontFamily: "var(--font-serif)", fontStyle: "italic" }}>
        {index}
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
      <Td align="right" style={{ fontVariantNumeric: "tabular-nums" }}>{n.article_count}</Td>
      <Td align="left" style={{ color: "var(--text-secondary)" }}>{formatDate(n.first_seen)}</Td>
      <Td align="left" style={{ color: "var(--text-secondary)" }}>{formatDate(n.last_seen)}</Td>
      <Td align="left">
        <span style={{
          display: "inline-block",
          padding: "0.15rem 0.5rem",
          borderRadius: 3,
          fontSize: "0.7rem",
          fontWeight: 500,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          background: n.status === "active" ? "var(--bg-badge-active)" : "var(--bg-badge-dormant)",
          color: n.status === "active" ? "var(--red)" : "var(--text-secondary)",
        }}>
          {n.status}
        </span>
      </Td>
    </tr>
  );
}

function Th({ children, align, width }: { children: React.ReactNode; align: "left" | "right"; width?: number }) {
  return (
    <th style={{
      textAlign: align,
      padding: "0.6rem 0.75rem",
      fontWeight: 500,
      fontSize: "0.7rem",
      letterSpacing: "0.1em",
      textTransform: "uppercase",
      color: "var(--text-secondary)",
      width,
    }}>
      {children}
    </th>
  );
}

function Td({ children, align, style }: { children: React.ReactNode; align: "left" | "right"; style?: React.CSSProperties }) {
  return (
    <td style={{
      textAlign: align,
      padding: "0.65rem 0.75rem",
      ...style,
    }}>
      {children}
    </td>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
