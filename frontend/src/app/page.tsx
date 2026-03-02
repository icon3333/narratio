"use client";

import { useEffect, useState } from "react";
import TimelineChart from "@/components/TimelineChart";
import NarrativeTable from "@/components/NarrativeTable";
import { fetchNarratives, fetchTimeline, triggerPipeline, Narrative, TimelinePoint } from "@/lib/api";

export default function Dashboard() {
  const [narratives, setNarratives] = useState<Narrative[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [mode, setMode] = useState<"attention" | "zscore">("attention");
  const [loading, setLoading] = useState(true);
  const [pipelineRunning, setPipelineRunning] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [n, t] = await Promise.all([fetchNarratives(), fetchTimeline()]);
      setNarratives(n);
      setTimeline(t);
    } catch (e) {
      console.error("Failed to load data:", e);
    }
    setLoading(false);
  }

  async function handleRunPipeline() {
    setPipelineRunning(true);
    try {
      await triggerPipeline();
      // Poll for completion
      const interval = setInterval(async () => {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/pipeline/status`
        );
        const status = await res.json();
        if (!status.running) {
          clearInterval(interval);
          setPipelineRunning(false);
          loadData();
        }
      }, 3000);
    } catch (e) {
      console.error("Pipeline failed:", e);
      setPipelineRunning(false);
    }
  }

  if (loading) {
    return <div className="text-gray-500 text-center py-20">Loading...</div>;
  }

  return (
    <div className="space-y-8">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setMode("attention")}
            className={`px-4 py-2 rounded text-sm ${mode === "attention" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
          >
            Share of Attention
          </button>
          <button
            onClick={() => setMode("zscore")}
            className={`px-4 py-2 rounded text-sm ${mode === "zscore" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
          >
            Z-Score Anomaly
          </button>
        </div>
        <button
          onClick={handleRunPipeline}
          disabled={pipelineRunning}
          className="px-4 py-2 rounded text-sm bg-green-700 text-white hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pipelineRunning ? "Running..." : "Run Pipeline"}
        </button>
      </div>

      {/* Timeline Chart */}
      <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
        <TimelineChart data={timeline} mode={mode} />
      </div>

      {/* Narrative Table */}
      <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Discovered Narratives</h2>
        <NarrativeTable narratives={narratives} />
      </div>
    </div>
  );
}
