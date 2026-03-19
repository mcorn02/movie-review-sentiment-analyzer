import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { ChartDistribution } from '../../types/report';

interface AspectRadarChartProps {
  distributions: ChartDistribution[];
}

function formatAspect(aspect: string) {
  return aspect.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function AspectRadarChart({ distributions }: AspectRadarChartProps) {
  const data = distributions.map(d => {
    const mentioned = d.positive + d.negative;
    const positivityScore = mentioned > 0 ? (d.positive / mentioned) * 100 : 0;
    return {
      aspect: formatAspect(d.aspect),
      score: Math.round(positivityScore),
    };
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis dataKey="aspect" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
        <Tooltip formatter={(value) => `${value}%`} />
        <Radar
          name="Positivity Score"
          dataKey="score"
          stroke="#3b82f6"
          fill="#3b82f6"
          fillOpacity={0.3}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
