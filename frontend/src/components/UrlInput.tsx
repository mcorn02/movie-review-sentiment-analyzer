import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

const DEFAULT_ASPECTS = [
  'acting_performances',
  'story_plot',
  'pacing',
  'visuals',
  'directing',
  'writing',
];

interface UrlInputProps {
  onSubmit: (url: string, aspects: string[]) => void;
  isLoading: boolean;
}

function isValidMovieUrl(url: string): boolean {
  return /imdb\.com\/title\/tt\d+/i.test(url);
}

export function UrlInput({ onSubmit, isLoading }: UrlInputProps) {
  const [url, setUrl] = useState('');
  const [selectedAspects, setSelectedAspects] = useState<string[]>(DEFAULT_ASPECTS);

  const isValid = isValidMovieUrl(url);

  function toggleAspect(aspect: string) {
    setSelectedAspects(prev =>
      prev.includes(aspect)
        ? prev.filter(a => a !== aspect)
        : [...prev, aspect]
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isValid && selectedAspects.length > 0 && !isLoading) {
      onSubmit(url, selectedAspects);
    }
  }

  function formatAspect(aspect: string) {
    return aspect.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="movie-url" className="block text-sm font-medium text-gray-300 mb-1">
          IMDB Movie URL
        </label>
        <div className="relative">
          <input
            id="movie-url"
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://www.imdb.com/title/tt1375666/"
            className="w-full px-4 py-3 pr-12 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
            disabled={isLoading}
          />
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        </div>
        {url && !isValid && (
          <p className="mt-1 text-sm text-red-500">
            Please enter a valid IMDB URL
          </p>
        )}
        {!url && (
          <p className="mt-1 text-xs text-gray-500">
            Accepts IMDB URLs (imdb.com/title/tt...)
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Aspects to Analyze
        </label>
        <div className="flex flex-wrap gap-2">
          {DEFAULT_ASPECTS.map(aspect => (
            <button
              key={aspect}
              type="button"
              onClick={() => toggleAspect(aspect)}
              disabled={isLoading}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                selectedAspects.includes(aspect)
                  ? 'bg-blue-900 text-blue-200 border border-blue-700'
                  : 'bg-gray-800 text-gray-400 border border-gray-700 hover:bg-gray-700'
              }`}
            >
              {formatAspect(aspect)}
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={!isValid || selectedAspects.length === 0 || isLoading}
        className="w-full py-3 px-6 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Analyzing...
          </>
        ) : (
          'Analyze Movie'
        )}
      </button>
    </form>
  );
}
