export type ButtonVariant = 'primary' | 'ghost'

const base =
  'inline-flex h-12 items-center justify-center rounded-pill px-6 text-body-xs font-medium ' +
  'transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'focus-visible:outline-paper-white disabled:cursor-not-allowed disabled:opacity-50'

const variants: Record<ButtonVariant, string> = {
  // White fill, dark text: the single highest-priority action in a viewport.
  primary: 'bg-paper-white text-obsidian hover:bg-bone',
  // Transparent with a 1px steel border: secondary actions.
  ghost: 'border border-steel bg-transparent text-paper-white hover:bg-carbon',
}

/** Class names for a pill button; also usable on links (e.g. React Router <Link>). */
export function buttonStyles(variant: ButtonVariant = 'primary', extra = ''): string {
  return `${base} ${variants[variant]} ${extra}`.trim()
}
