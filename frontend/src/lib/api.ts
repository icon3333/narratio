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
  significance_score: number | null;
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
  sources_breakdown: { source: string; count: number; first_article: string; last_article: string }[];
}

export interface ArisingNarrative {
  id: number;
  label: string;
  first_seen: string;
  status: string;
  arising_score: number;
  latest_share: number | null;
  article_count_total: number;
  article_count_latest: number;
  weeks_active: number;
  growth_trend: "accelerating" | "steady" | "fading";
  weekly_articles: number[];
}

export interface PipelineStatus {
  running: boolean;
  last_result: string | null;
  step: number;
  total_steps: number;
  step_label: string;
}

export interface Cover {
  id: number;
  date: string;
  title: string | null;
  image_url: string;
  edition_url: string | null;
  year: number;
}

export interface CoversResponse {
  covers: Cover[];
  total: number;
  page: number;
  per_page: number;
  years: number[];
}

export interface MapCountryNarrative {
  narrative_id: number;
  label: string;
  count: number;
}

export interface MapCountry {
  country_code: string;
  country_name: string;
  article_count: number;
  share: number;
  top_narratives: MapCountryNarrative[];
}

export interface DateRange {
  min_date: string | null;
  max_date: string | null;
}

// ---- Shared helpers ----

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

function buildParams(obj: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(obj))
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  return sp.toString();
}

// ---- API functions ----

export const fetchNarratives = () =>
  fetchJson<Narrative[]>(`${API_BASE}/api/narratives`);

export function fetchTimeline(params?: {
  start?: string;
  end?: string;
  narratives?: number[];
  top_n?: number;
}): Promise<TimelinePoint[]> {
  const qs = buildParams({
    start: params?.start,
    end: params?.end,
    narratives: params?.narratives?.join(","),
    top_n: params?.top_n,
  });
  return fetchJson(`${API_BASE}/api/timeline?${qs}`);
}

export const fetchNarrativeDetail = (id: number) =>
  fetchJson<NarrativeDetail>(`${API_BASE}/api/narratives/${id}`);

export const fetchHeadlines = (id: number, limit = 10) =>
  fetchJson<Headline[]>(`${API_BASE}/api/narratives/${id}/headlines?limit=${limit}`);

export const fetchSources = () =>
  fetchJson<string[]>(`${API_BASE}/api/sources`);

export function fetchArticles(params?: {
  page?: number;
  per_page?: number;
  source?: string;
  search?: string;
}): Promise<ArticlesResponse> {
  const qs = buildParams({
    page: params?.page,
    per_page: params?.per_page,
    source: params?.source,
    search: params?.search,
  });
  return fetchJson(`${API_BASE}/api/articles?${qs}`);
}

export const fetchStats = () =>
  fetchJson<Stats>(`${API_BASE}/api/stats`);

export const fetchArising = () =>
  fetchJson<ArisingNarrative[]>(`${API_BASE}/api/arising`);

export const triggerPipeline = () =>
  fetchJson<{ status: string }>(`${API_BASE}/api/pipeline/run`, { method: "POST" });

export const triggerAnalysis = () =>
  fetchJson<{ status: string }>(`${API_BASE}/api/pipeline/analyze`, { method: "POST" });

export const fetchPipelineStatus = () =>
  fetchJson<PipelineStatus>(`${API_BASE}/api/pipeline/status`);

// ---- Map ----

export function fetchMapData(params?: { start?: string; end?: string }): Promise<MapCountry[]> {
  const qs = buildParams({ start: params?.start, end: params?.end });
  return fetchJson(`${API_BASE}/api/map?${qs}`);
}

export const fetchDateRange = () =>
  fetchJson<DateRange>(`${API_BASE}/api/date-range`);

// ---- Economist Covers ----

export function coverImageUrl(url: string, thumb = false): string {
  const optimized = thumb
    ? url.replace("width=1424", "width=400").replace("quality=80", "quality=70")
    : url;
  return `${API_BASE}/api/covers/image-proxy?url=${encodeURIComponent(optimized)}`;
}

export function fetchCovers(year?: number, page?: number, perPage?: number): Promise<CoversResponse> {
  const qs = buildParams({ year, page, per_page: perPage });
  return fetchJson(`${API_BASE}/api/covers?${qs}`);
}

export function refreshCovers(year?: number): Promise<{ status: string; year: number }> {
  const qs = buildParams({ year });
  return fetchJson(`${API_BASE}/api/covers/refresh?${qs}`, { method: "POST" });
}
