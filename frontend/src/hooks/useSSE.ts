import { useState, useCallback, useRef } from 'react';
import type {
  PipelineStage,
  StageEvent,
  ChartDistribution,
  ReportData,
  AspectReport,
} from '../types/report';

interface SSEState {
  stage: PipelineStage;
  stageMessage: string;
  progress: number;
  total: number;
  movieTitle: string;
  distributions: ChartDistribution[];
  report: ReportData | null;
  completedAspects: AspectReport[];
  error: string | null;
  warning: string | null;
}

const initialState: SSEState = {
  stage: 'idle',
  stageMessage: '',
  progress: 0,
  total: 0,
  movieTitle: '',
  distributions: [],
  report: null,
  completedAspects: [],
  error: null,
  warning: null,
};

export function useSSE() {
  const [state, setState] = useState<SSEState>(initialState);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setState(initialState);
    setIsRunning(false);
  }, []);

  const startReport = useCallback(async (imdbUrl: string, aspects?: string[]) => {
    // Abort any existing request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    setState(initialState);
    setIsRunning(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const body: Record<string, unknown> = { imdb_url: imdbUrl };
      if (aspects && aspects.length > 0) {
        body.aspects = aspects;
      }

      const response = await fetch('/api/report/imdb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6));
              handleEvent(currentEvent, data);
            } catch {
              // Skip malformed JSON
            }
            currentEvent = '';
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setState(prev => ({
        ...prev,
        stage: 'error',
        error: err instanceof Error ? err.message : 'Unknown error',
      }));
    } finally {
      setIsRunning(false);
    }
  }, []);

  function handleEvent(event: string, data: Record<string, unknown>) {
    switch (event) {
      case 'stage': {
        const stageData = data as unknown as StageEvent;
        setState(prev => ({
          ...prev,
          stage: stageData.stage,
          stageMessage: stageData.message || prev.stageMessage,
          progress: stageData.progress ?? prev.progress,
          total: stageData.total ?? prev.total,
          movieTitle: stageData.movie_title || prev.movieTitle,
        }));
        break;
      }
      case 'aspect_complete': {
        const aspect = data as unknown as AspectReport;
        setState(prev => ({
          ...prev,
          completedAspects: [...prev.completedAspects, aspect],
        }));
        break;
      }
      case 'charts': {
        const charts = data as { distributions: ChartDistribution[] };
        setState(prev => ({
          ...prev,
          distributions: charts.distributions,
        }));
        break;
      }
      case 'report': {
        const report = data as unknown as ReportData;
        setState(prev => ({
          ...prev,
          report,
        }));
        break;
      }
      case 'warning': {
        const warning = data as { message: string };
        setState(prev => ({
          ...prev,
          warning: warning.message,
        }));
        break;
      }
      case 'error': {
        const error = data as { message: string };
        setState(prev => ({
          ...prev,
          stage: 'error',
          error: error.message,
        }));
        break;
      }
      case 'done': {
        const done = data as { status: string };
        setState(prev => ({
          ...prev,
          stage: done.status === 'complete' ? 'done' : 'error',
        }));
        break;
      }
    }
  }

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setIsRunning(false);
  }, []);

  return { ...state, isRunning, startReport, cancel, reset };
}
