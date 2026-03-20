import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ChartDistribution } from '../../types/report';

interface SentimentBarChartProps {
  distributions: ChartDistribution[];
}

function formatAspect(aspect: string) {
  return aspect.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function SentimentBarChart({ distributions }: SentimentBarChartProps) {
  const hasLowCoverage = distributions.some(d => (d.positive_pct + d.negative_pct) < 20);

  const data = distributions.map(d => {
    const mentioned = d.positive + d.negative;
    const mentionRate = d.positive_pct + d.negative_pct;
    const posOfMentioned = mentioned > 0 ? (d.positive / mentioned) * 100 : 0;
    const negOfMentioned = mentioned > 0 ? (d.negative / mentioned) * 100 : 0;
    const label = mentionRate < 20 ? `${formatAspect(d.aspect)} *` : formatAspect(d.aspect);
    return {
      aspect: label,
      Positive: Math.round(posOfMentioned * 10) / 10,
      Negative: Math.round(negOfMentioned * 10) / 10,
      mentionRate: Math.round(mentionRate),
    };
  });

  return (
    <div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="aspect" tick={{ fontSize: 12, fill: '#9ca3af' }} />
          <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} unit="%" domain={[0, 100]} label={{ value: '% of Mentioned Reviews', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 11 }, dy: 60 }} />
          <Tooltip
            formatter={(value, name, props) => {
              const mentionRate = props.payload?.mentionRate;
              const suffix = mentionRate !== undefined && mentionRate < 20
                ? ` (⚠ only ${mentionRate}% mentioned)`
                : mentionRate !== undefined
                  ? ` (${mentionRate}% mentioned)`
                  : '';
              return [`${Number(value).toFixed(1)}%${suffix}`, name];
            }}
            contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#f9fafb', borderRadius: '8px' }}
          />
          <Legend />
          <Bar dataKey="Positive" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} />
          <Bar dataKey="Negative" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {hasLowCoverage && (
        <p className="text-xs text-gray-500 mt-2 text-center">
          * Fewer than 20% of reviews mentioned this aspect — data may be limited.
        </p>
      )}
    </div>
  );
}
