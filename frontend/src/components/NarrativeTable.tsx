"use client";

import Link from "next/link";
import { Narrative } from "@/lib/api";

interface Props {
  narratives: Narrative[];
}

export default function NarrativeTable({ narratives }: Props) {
  if (narratives.length === 0) {
    return <div className="text-gray-500 text-center py-8">No narratives discovered yet</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-400">
            <th className="text-left py-3 px-4">#</th>
            <th className="text-left py-3 px-4">Narrative</th>
            <th className="text-right py-3 px-4">Articles</th>
            <th className="text-left py-3 px-4">First Seen</th>
            <th className="text-left py-3 px-4">Last Seen</th>
            <th className="text-left py-3 px-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {narratives.map((n, i) => (
            <tr key={n.id} className="border-b border-gray-800/50 hover:bg-gray-900/50">
              <td className="py-3 px-4 text-gray-500">{i + 1}</td>
              <td className="py-3 px-4">
                <Link href={`/narratives/${n.id}`} className="text-blue-400 hover:text-blue-300 font-medium">
                  {n.label}
                </Link>
              </td>
              <td className="py-3 px-4 text-right">{n.article_count}</td>
              <td className="py-3 px-4 text-gray-400">{n.first_seen}</td>
              <td className="py-3 px-4 text-gray-400">{n.last_seen}</td>
              <td className="py-3 px-4">
                <span className={`px-2 py-0.5 rounded text-xs ${n.status === "active" ? "bg-green-900/50 text-green-400" : "bg-gray-800 text-gray-500"}`}>
                  {n.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
