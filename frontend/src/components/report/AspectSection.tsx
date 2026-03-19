import { Card, CardBody } from '../ui/Card';
import { Badge } from '../ui/Badge';
import type { AspectReport } from '../../types/report';

interface AspectSectionProps {
  aspect: AspectReport;
}

function formatAspect(aspect: string) {
  return aspect.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function AspectSection({ aspect }: AspectSectionProps) {
  const { distribution } = aspect;
  const total =
    distribution.positive.count +
    distribution.negative.count +
    distribution.not_mentioned.count;

  const posPct = distribution.positive.pct;
  const negPct = distribution.negative.pct;

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            {formatAspect(aspect.name)}
          </h3>
          <div className="flex gap-2">
            <Badge variant="positive">{posPct}% positive</Badge>
            <Badge variant="negative">{negPct}% negative</Badge>
          </div>
        </div>

        {/* Mini horizontal bar */}
        <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden flex">
          {posPct > 0 && (
            <div
              className="bg-green-500 h-full"
              style={{ width: `${posPct}%` }}
            />
          )}
          {negPct > 0 && (
            <div
              className="bg-red-500 h-full"
              style={{ width: `${negPct}%` }}
            />
          )}
        </div>

        <p className="text-gray-700 text-sm leading-relaxed">{aspect.narrative}</p>

        {aspect.top_quotes.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Top Quotes ({total} reviews)
            </p>
            {aspect.top_quotes.slice(0, 3).map((q, i) => (
              <blockquote
                key={i}
                className="text-sm text-gray-600 italic border-l-2 border-gray-300 pl-3"
              >
                "{q.sentence}"
                <span className="text-xs text-gray-400 not-italic ml-1">
                  — Review #{q.review}
                </span>
              </blockquote>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
