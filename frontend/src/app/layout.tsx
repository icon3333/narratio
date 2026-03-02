import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";
import ThemeToggle from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "Narratio — Narrative Radar",
  description: "Track the stories markets tell themselves",
};

const FOUC_SCRIPT = `(function(){var s=localStorage.getItem('theme');var p=window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';document.documentElement.setAttribute('data-theme',s||p)})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="color-scheme" content="light dark" />
        <script dangerouslySetInnerHTML={{ __html: FOUC_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <header
            style={{
              position: "sticky",
              top: 0,
              zIndex: 100,
              borderBottom: "1px solid var(--border)",
              backdropFilter: "blur(12px)",
              background: "var(--bg-header)",
            }}
          >
            <div
              style={{
                maxWidth: 1080,
                margin: "0 auto",
                padding: "1.25rem 1.5rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <a href="/" style={{ textDecoration: "none" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                  <h1
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: "1.35rem",
                      fontWeight: 700,
                      letterSpacing: "-0.01em",
                      color: "var(--text-primary)",
                      lineHeight: 1.1,
                    }}
                  >
                    Narrat<span style={{ color: "var(--red)" }}>io</span>
                  </h1>
                  <div
                    style={{
                      fontSize: "0.7rem",
                      letterSpacing: "0.15em",
                      textTransform: "uppercase",
                      color: "var(--text-secondary)",
                      fontWeight: 400,
                      fontFamily: "var(--font-sans)",
                    }}
                  >
                    Narrative Radar
                  </div>
                </div>
              </a>
              <ThemeToggle />
            </div>
          </header>
          <main style={{ maxWidth: 1080, margin: "0 auto", padding: "2rem 1.5rem 4rem" }}>
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
