import { Check, Loader2, Search, BarChart3, FileText } from 'lucide-react';
import type { PipelineStage } from '../types/report';

interface ProgressStepperProps {
  stage: PipelineStage;
  stageMessage: string;
  progress: number;
  total: number;
}

const steps = [
  { key: 'scraping' as const, label: 'Scraping Reviews', icon: Search },
  { key: 'analyzing' as const, label: 'Analyzing Sentiment', icon: BarChart3 },
  { key: 'generating' as const, label: 'Generating Report', icon: FileText },
];

const stageOrder: Record<string, number> = {
  scraping: 0,
  analyzing: 1,
  generating: 2,
  done: 3,
};

export function ProgressStepper({ stage, stageMessage, progress, total }: ProgressStepperProps) {
  const currentIndex = stageOrder[stage] ?? -1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        {steps.map((step, idx) => {
          const isComplete = currentIndex > idx;
          const isCurrent = currentIndex === idx;
          const Icon = step.icon;

          return (
            <div key={step.key} className="flex items-center flex-1">
              <div className="flex items-center gap-2">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                    isComplete
                      ? 'bg-green-500 text-white'
                      : isCurrent
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-800 text-gray-500'
                  }`}
                >
                  {isComplete ? (
                    <Check className="w-5 h-5" />
                  ) : isCurrent ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>
                <span
                  className={`text-sm font-medium ${
                    isComplete || isCurrent ? 'text-white' : 'text-gray-500'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-4 ${
                    currentIndex > idx ? 'bg-green-500' : 'bg-gray-800'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {stageMessage && (
        <div className="text-center">
          <p className="text-sm text-gray-400">{stageMessage}</p>
          {total > 0 && (
            <div className="mt-2 w-full bg-gray-800 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.min((progress / total) * 100, 100)}%` }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
