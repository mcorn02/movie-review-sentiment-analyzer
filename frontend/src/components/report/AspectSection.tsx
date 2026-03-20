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
  const mentionRate = posPct + negPct;

  const posOfMentioned = mentionRate > 0 ? Math.round((posPct / mentionRate) * 100) : 0;
  const negOfMentioned = mentionRate > 0 ? Math.round((negPct / mentionRate) * 100) : 0;

  const showBadgesOfMentioned = mentionRate < 50;

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">
            {formatAspect(aspect.name)}
          </h3>
          <div className="flex gap-2">
            {showBadgesOfMentioned ? (
              <>
                <Badge variant="positive">+{posOfMentioned}% of mentions</Badge>
                <Badge variant="negative">-{negOfMentioned}% of mentions</Badge>
              </>
            ) : (
              <>
                <Badge variant="positive">{posPct}% positive</Badge>
                <Badge variant="negative">{negPct}% negative</Badge>
              </>
            )}
          </div>
        </div>

        {/* Low coverage warning */}
        {mentionRate < 20 && (
          <div className="bg-yellow-950 border border-yellow-800 text-yellow-300 text-xs rounded-md px-3 py-2 flex items-center gap-2">
            <span>⚠</span>
            <span>Only {Math.round(mentionRate)}% of reviews mentioned this aspect. Sentiment data may not be representative.</span>
          </div>
        )}

        {/* Mini horizontal bar */}
        <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden flex">
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

        {/* Moderate coverage note */}
        {mentionRate >= 20 && mentionRate < 50 && (
          <p className="text-xs text-gray-500">{Math.round(mentionRate)}% of reviews mentioned this aspect</p>
        )}

        <p className="text-gray-300 text-sm leading-relaxed">{aspect.narrative}</p>

        {aspect.top_quotes.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-gray-800">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              Top Quotes ({total} reviews)
            </p>
            {aspect.top_quotes.slice(0, 3).map((q, i) => (
              <blockquote
                key={i}
                className="text-sm text-gray-400 italic border-l-2 border-gray-600 pl-3"
              >
                "{q.sentence}"
                <span className="text-xs text-gray-500 not-italic ml-1">
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
