export interface SentimentDistribution {
  positive: { count: number; pct: number };
  negative: { count: number; pct: number };
  not_mentioned: { count: number; pct: number };
}

export interface TopQuote {
  sentence: string;
  review: number;
}

export interface AspectReport {
  name: string;
  distribution: SentimentDistribution;
  narrative: string;
  top_quotes: TopQuote[];
}

export interface ChartDistribution {
  aspect: string;
  positive: number;
  negative: number;
  not_mentioned: number;
  positive_pct: number;
  negative_pct: number;
  not_mentioned_pct: number;
}

export interface ReportData {
  overall_summary: string;
  movie_title: string;
  n_reviews: number;
  aspects: AspectReport[];
}

export type PipelineStage = 'idle' | 'scraping' | 'analyzing' | 'generating' | 'done' | 'error';

export interface StageEvent {
  stage: PipelineStage;
  message?: string;
  progress?: number;
  total?: number;
  movie_title?: string;
}
