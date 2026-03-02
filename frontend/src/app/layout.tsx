import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Narratio — Narrative Radar",
  description: "Track the stories markets tell themselves",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <header className="border-b border-gray-800 px-6 py-4">
          <a href="/" className="text-xl font-bold text-white">
            Narratio <span className="text-sm font-normal text-gray-400">Narrative Radar</span>
          </a>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
