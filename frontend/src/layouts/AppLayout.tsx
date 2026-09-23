import { Link, Outlet } from 'react-router-dom'
import ApiHealthBadge from '../components/ui/ApiHealthBadge'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:rounded-pill focus:bg-paper-white focus:px-4 focus:py-2 focus:text-obsidian"
      >
        Skip to content
      </a>

      <header className="border-b border-graphite">
        <div className="mx-auto flex h-16 w-full max-w-[var(--page-max-width)] items-center px-6">
          <Link
            to="/"
            className="font-ivy-presto text-subheading text-paper-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-paper-white"
          >
            RepoMentor
          </Link>
        </div>
      </header>

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-graphite">
        <div className="mx-auto flex w-full max-w-[var(--page-max-width)] flex-wrap items-center justify-between gap-4 px-6 py-6">
          <ApiHealthBadge />
          <p className="text-eyebrow text-fog">Read-only analysis. Repository code is never executed.</p>
        </div>
      </footer>
    </div>
  )
}
