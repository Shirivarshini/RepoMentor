import { CircleAlert, CircleCheck, LoaderCircle } from 'lucide-react'
import { useApiHealth } from '../../hooks/useApiHealth'

/**
 * Compact API status badge. State is conveyed by text and icon, never color alone.
 * (Semantic status colors are introduced with the dashboard in Phase 8.)
 */
export default function ApiHealthBadge() {
  const { isPending, isError } = useApiHealth()

  let label = 'API ok'
  let icon = <CircleCheck aria-hidden="true" className="size-3.5" />
  if (isPending) {
    label = 'Checking API'
    icon = <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
  } else if (isError) {
    label = 'API unreachable'
    icon = <CircleAlert aria-hidden="true" className="size-3.5" />
  }

  return (
    <span
      role="status"
      className="inline-flex items-center gap-2 rounded-pill border border-slate px-3 py-1.5 text-eyebrow uppercase tracking-[0.08em] text-silver"
    >
      {icon}
      {label}
    </span>
  )
}
