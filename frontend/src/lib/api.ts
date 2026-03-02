const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Narrative {
  id: number;
  label: string;
  article_count: number;
  first_seen: string;
  last_seen: string;
  status: string;
  significance_score: number | null;
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
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchTimeline(params?: {
  start?: string;
  end?: string;
  narratives?: number[];
  top_n?: number;
}): Promise<TimelinePoint[]> {
  const searchParams = new URLSearchParams();
  if (params?.start) searchParams.set("start", params.start);
  if (params?.end) searchParams.set("end", params.end);
  if (params?.narratives) searchParams.set("narratives", params.narratives.join(","));
  if (params?.top_n) searchParams.set("top_n", params.top_n.toString());
  const res = await fetch(`${API_BASE}/api/timeline?${searchParams}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchNarrativeDetail(id: number): Promise<NarrativeDetail> {
  const res = await fetch(`${API_BASE}/api/narratives/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchHeadlines(id: number, limit = 10): Promise<Headline[]> {
  const res = await fetch(`${API_BASE}/api/narratives/${id}/headlines?limit=${limit}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface Article {
  headline: string;
  source: string;
  url: string;
  published_at: string;
}

export interface ArticlesResponse {
  articles: Article[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  total_articles: number;
  total_narratives: number;
  active_narratives: number;
  dormant_narratives: number;
  first_article_date: string | null;
  last_article_date: string | null;
  noise_count: number;
  top_by_significance: { id: number; label: string; significance_score: number }[];
  biggest_movers: { id: number; label: string; z_score: number }[];
  longest_running: { id: number; label: string; first_seen: string; last_seen: string; duration_days: number }[];
}

export async function fetchArticles(params?: {
  page?: number;
  per_page?: number;
  source?: string;
  search?: string;
}): Promise<ArticlesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", params.page.toString());
  if (params?.per_page) searchParams.set("per_page", params.per_page.toString());
  if (params?.source) searchParams.set("source", params.source);
  if (params?.search) searchParams.set("search", params.search);
  const res = await fetch(`${API_BASE}/api/articles?${searchParams}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface PipelineStatus {
  running: boolean;
  last_result: string | null;
  step: number;
  total_steps: number;
  step_label: string;
}

export async function triggerPipeline(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, { method: "POST" });
  if (!res.ok) throw new Error(`Pipeline trigger failed: ${res.status}`);
  return res.json();
}

export async function triggerAnalysis(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/pipeline/analyze`, { method: "POST" });
  if (!res.ok) throw new Error(`Analysis trigger failed: ${res.status}`);
  return res.json();
}

export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${API_BASE}/api/pipeline/status`);
  if (!res.ok) throw new Error(`Pipeline status failed: ${res.status}`);
  return res.json();
}
