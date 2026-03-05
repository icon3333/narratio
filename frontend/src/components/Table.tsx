import React from "react";

export function Th({
  children,
  align,
  width,
}: {
  children: React.ReactNode;
  align: "left" | "right" | "center";
  width?: number;
}) {
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
        width,
      }}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align,
  style,
}: {
  children: React.ReactNode;
  align: "left" | "right" | "center";
  style?: React.CSSProperties;
}) {
  return (
    <td style={{ textAlign: align, padding: "0.65rem 0.75rem", ...style }}>
      {children}
    </td>
  );
}
