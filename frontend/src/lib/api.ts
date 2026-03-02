const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Narrative {
  id: number;
  label: string;
  article_count: number;
  first_seen: string;
  last_seen: string;
  status: string;
}

export interface TimelinePoint {
  narrative_id: number;
  label: string;
  week_start: string;
  article_count: number;
  share_of_attention: number;
  z_score: number | null;
  sentiment_mean: number | null;
}

export interface NarrativeWeek {
  narrative_id: number;
  week_start: string;
  article_count: number;
  share_of_attention: number | null;
  z_score: number | null;
  sentiment_mean: number | null;
  summary: string | null;
  top_headline_ids: string | null;
}

export interface NarrativeDetail {
  id: number;
  label: string;
  first_seen: string;
  last_seen: string;
  status: string;
  weeks: NarrativeWeek[];
}

export interface Headline {
  headline: string;
  source: string;
  url: string;
  published_at: string;
  sentiment_score: number | null;
  sentiment_label: string | null;
}

export async function fetchNarratives(): Promise<Narrative[]> {
  const res = await fetch(`${API_BASE}/api/narratives`);
  return res.json();
}

export async function fetchTimeline(params?: {
  start?: string;
  end?: string;
  narratives?: number[];
}): Promise<TimelinePoint[]> {
  const searchParams = new URLSearchParams();
  if (params?.start) searchParams.set("start", params.start);
  if (params?.end) searchParams.set("end", params.end);
  if (params?.narratives) searchParams.set("narratives", params.narratives.join(","));
  const res = await fetch(`${API_BASE}/api/timeline?${searchParams}`);
  return res.json();
}

export async function fetchNarrativeDetail(id: number): Promise<NarrativeDetail> {
  const res = await fetch(`${API_BASE}/api/narratives/${id}`);
  return res.json();
}

export async function fetchHeadlines(id: number, limit = 10): Promise<Headline[]> {
  const res = await fetch(`${API_BASE}/api/narratives/${id}/headlines?limit=${limit}`);
  return res.json();
}

export async function triggerPipeline(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, { method: "POST" });
  return res.json();
}
