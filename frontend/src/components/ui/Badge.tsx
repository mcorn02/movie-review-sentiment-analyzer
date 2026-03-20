import type { ReactNode } from 'react';

const variants = {
  positive: 'bg-green-900 text-green-300',
  negative: 'bg-red-900 text-red-300',
  neutral: 'bg-gray-800 text-gray-300',
  info: 'bg-blue-900 text-blue-300',
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
