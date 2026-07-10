export default function Spinner({ size = 'md', className = '' }) {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-[3px]',
    xl: 'w-16 h-16 border-4',
  }

  return (
    <div
      className={`rounded-full border-transparent border-t-accent animate-spin ${sizeClasses[size] || sizeClasses.md} ${className}`}
      role="status"
      aria-label="Loading"
    />
  )
}
