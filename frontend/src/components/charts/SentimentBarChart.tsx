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
  const data = distributions.map(d => ({
    aspect: formatAspect(d.aspect),
    Positive: d.positive_pct,
    Negative: d.negative_pct,
    'Not Mentioned': d.not_mentioned_pct,
  }));

  return (
    <ResponsiveContainer width="100%" height={350}>
      <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="aspect" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} unit="%" />
        <Tooltip
          formatter={(value) => `${Number(value).toFixed(1)}%`}
          contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }}
        />
        <Legend />
        <Bar dataKey="Positive" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} />
        <Bar dataKey="Negative" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
        <Bar dataKey="Not Mentioned" stackId="a" fill="#d1d5db" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
