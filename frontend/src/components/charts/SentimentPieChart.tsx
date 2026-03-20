import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { ChartDistribution } from '../../types/report';

interface SentimentPieChartProps {
  distributions: ChartDistribution[];
}

const COLORS = {
  Positive: '#22c55e',
  Negative: '#ef4444',
};

export function SentimentPieChart({ distributions }: SentimentPieChartProps) {
  // Aggregate only mentioned reviews across all aspects
  const totals = distributions.reduce(
    (acc, d) => ({
      positive: acc.positive + d.positive,
      negative: acc.negative + d.negative,
    }),
    { positive: 0, negative: 0 }
  );

  const data = [
    { name: 'Positive', value: totals.positive },
    { name: 'Negative', value: totals.negative },
  ].filter(d => d.value > 0);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={3}
          dataKey="value"
          label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map(entry => (
            <Cell
              key={entry.name}
              fill={COLORS[entry.name as keyof typeof COLORS]}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#f9fafb', borderRadius: '8px' }}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
