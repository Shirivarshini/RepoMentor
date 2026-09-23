import { Link } from 'react-router-dom'
import { buttonStyles } from '../components/ui/buttonStyles'

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex w-full max-w-[var(--page-max-width)] flex-col items-start gap-6 px-6 py-28">
      <p className="text-eyebrow uppercase tracking-[0.14em] text-copper">404</p>
      <h1 className="font-ivy-presto text-heading-sm text-paper-white">Page not found</h1>
      <p className="max-w-xl text-body-sm text-fog">
        The page you are looking for does not exist.
      </p>
      <Link to="/" className={buttonStyles('ghost')}>
        Back to home
      </Link>
    </div>
  )
}
