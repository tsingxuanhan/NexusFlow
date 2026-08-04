import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  icon?: ReactNode
  action?: ReactNode
}

export function Card({ children, className = '', title, icon, action }: CardProps) {
  return (
    <div className={`bg-white rounded-xl border border-gray-100 shadow-sm ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div className="flex items-center gap-2">
            {icon && <span className="text-[#6366f1]">{icon}</span>}
            {title && <h3 className="text-sm font-semibold text-gray-800">{title}</h3>}
          </div>
          {action}
        </div>
      )}
      <div className="px-5 pb-4">{children}</div>
    </div>
  )
}
