import type { ReactNode } from 'react';

const variants = {
  positive: 'bg-green-100 text-green-800',
  negative: 'bg-red-100 text-red-800',
  neutral: 'bg-gray-100 text-gray-800',
  info: 'bg-blue-100 text-blue-800',
} as const;

interface BadgeProps {
  children: ReactNode;
  variant?: keyof typeof variants;
}

export function Badge({ children, variant = 'neutral' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]}`}>
      {children}
    </span>
  );
}
