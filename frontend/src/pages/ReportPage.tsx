import { useSSE } from '../hooks/useSSE';
import { UrlInput } from '../components/UrlInput';
import { ProgressStepper } from '../components/ProgressStepper';
import { SentimentBarChart } from '../components/charts/SentimentBarChart';
import { SentimentPieChart } from '../components/charts/SentimentPieChart';
import { AspectRadarChart } from '../components/charts/AspectRadarChart';
import { ReportCard } from '../components/report/ReportCard';
import { AspectSection } from '../components/report/AspectSection';
import { Card, CardHeader, CardBody } from '../components/ui/Card';
import { AlertTriangle, XCircle } from 'lucide-react';

export function ReportPage() {
  const sse = useSSE();

  const showProgress = sse.isRunning || sse.stage === 'done';
  const showCharts = sse.distributions.length > 0;
  const showReport = sse.report !== null;
  const aspects = sse.report?.aspects ?? sse.completedAspects;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">
            Movie Review Analyzer
          </h1>
          <p className="text-gray-500 mt-1">
            Paste an IMDB URL to analyze movie reviews with AI-powered sentiment analysis
          </p>
        </div>

        {/* Input Form */}
        <Card>
          <CardBody>
            <UrlInput onSubmit={sse.startReport} isLoading={sse.isRunning} />
          </CardBody>
        </Card>

        {/* Warning */}
        {sse.warning && (
          <div className="flex items-center gap-2 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            {sse.warning}
          </div>
        )}

        {/* Error */}
        {sse.error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            <XCircle className="w-5 h-5 shrink-0" />
            {sse.error}
          </div>
        )}

        {/* Progress */}
        {showProgress && (
          <Card>
            <CardBody>
              <ProgressStepper
                stage={sse.stage}
                stageMessage={sse.stageMessage}
                progress={sse.progress}
                total={sse.total}
              />
            </CardBody>
          </Card>
        )}

        {/* Charts */}
        {showCharts && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold text-gray-900">
                  Sentiment by Aspect
                </h2>
              </CardHeader>
              <CardBody>
                <SentimentBarChart distributions={sse.distributions} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold text-gray-900">
                  Overall Sentiment
                </h2>
              </CardHeader>
              <CardBody>
                <SentimentPieChart distributions={sse.distributions} />
              </CardBody>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <h2 className="text-lg font-semibold text-gray-900">
                  Positivity Radar
                </h2>
                <p className="text-sm text-gray-500">
                  Positivity score per aspect (% of mentioned reviews that are positive)
                </p>
              </CardHeader>
              <CardBody>
                <AspectRadarChart distributions={sse.distributions} />
              </CardBody>
            </Card>
          </div>
        )}

        {/* Report */}
        {showReport && sse.report && (
          <div className="space-y-6">
            <ReportCard
              movieTitle={sse.report.movie_title}
              nReviews={sse.report.n_reviews}
              overallSummary={sse.report.overall_summary}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {aspects.map(aspect => (
                <AspectSection key={aspect.name} aspect={aspect} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
