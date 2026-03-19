import { Film } from 'lucide-react';
import { Card, CardBody } from '../ui/Card';

interface ReportCardProps {
  movieTitle: string;
  nReviews: number;
  overallSummary: string;
}

export function ReportCard({ movieTitle, nReviews, overallSummary }: ReportCardProps) {
  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardBody>
        <div className="flex items-start gap-3 mb-3">
          <Film className="w-6 h-6 text-blue-500 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-xl font-bold text-gray-900">{movieTitle}</h2>
            <p className="text-sm text-gray-500">Based on {nReviews} reviews</p>
          </div>
        </div>
        <p className="text-gray-700 leading-relaxed">{overallSummary}</p>
      </CardBody>
    </Card>
  );
}
