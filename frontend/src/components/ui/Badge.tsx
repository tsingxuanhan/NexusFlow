interface BadgeProps {
  children: React.ReactNode
  color?: string
}

const colors: Record<string, string> = {
  indigo: 'bg-indigo-50 text-[#6366f1] border-indigo-200',
  green: 'bg-emerald-50 text-[#10B981] border-emerald-200',
  orange: 'bg-orange-50 text-[#F97316] border-orange-200',
  sky: 'bg-sky-50 text-[#0EA5E9] border-sky-200',
  gray: 'bg-gray-50 text-gray-600 border-gray-200',
  red: 'bg-red-50 text-red-600 border-red-200',
  yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
}

export function Badge({ children, color = 'indigo' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${colors[color] || colors.gray}`}>
      {children}
    </span>
  )
}
