import Button from '../ui/Button'

/**
 * Landing-page repository input (placeholder).
 * Disabled until repository analysis is implemented; it is the layout and copy from docs/DESIGN.md.
 */
export default function RepositoryInput() {
  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="repository-url" className="sr-only">
        Public GitHub repository URL
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="repository-url"
          type="url"
          disabled
          aria-describedby="repository-url-note"
          placeholder="Paste a public GitHub repository URL"
          className="h-12 w-full rounded-pill border border-slate bg-carbon px-6 text-body-xs text-bone placeholder:text-fog disabled:cursor-not-allowed disabled:opacity-70"
        />
        <Button disabled className="shrink-0">
          Analyze Repository
        </Button>
      </div>
      <p id="repository-url-note" className="text-eyebrow text-fog">
        Repository analysis is not available in this build yet.
      </p>
    </div>
  )
}
