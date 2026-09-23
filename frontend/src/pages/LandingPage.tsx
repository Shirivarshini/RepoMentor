import PipelinePreview from '../components/repository/PipelinePreview'
import RepositoryInput from '../components/repository/AnalyzeForm'

export default function LandingPage() {
  return (
    <div className="landing-shell">
      <div className="flex flex-col gap-6">
        <p className="text-eyebrow uppercase tracking-[0.14em] text-copper">
          Repository onboarding
        </p>
        <h1 className="font-ivy-presto text-heading-sm text-paper-white lg:text-heading-lg">
          Understand any codebase before you touch it.
        </h1>
        <p className="max-w-xl text-body-sm text-fog">
          Paste a public GitHub repository and get architecture, modules, files, setup guidance,
          and repository-grounded answers.
        </p>
        <div className="mt-2 max-w-xl">
          <RepositoryInput />
        </div>
      </div>

      <PipelinePreview />
    </div>
  )
}
