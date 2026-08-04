import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md'
}

const variants: Record<Variant, string> = {
  primary: 'bg-[#6366f1] text-white hover:bg-[#4f46e5] shadow-sm',
  secondary: 'bg-white text-[#1E293B] border border-gray-200 hover:bg-gray-50',
  danger: 'bg-[#F97316] text-white hover:bg-[#ea580c] shadow-sm',
  ghost: 'text-gray-500 hover:text-[#6366f1] hover:bg-indigo-50',
}

export function Button({ variant = 'primary', size = 'md', className = '', children, ...props }: ButtonProps) {
  const sizeClass = size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'
  return (
    <button
      className={`rounded-lg font-medium transition-all duration-200 cursor-pointer ${sizeClass} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
