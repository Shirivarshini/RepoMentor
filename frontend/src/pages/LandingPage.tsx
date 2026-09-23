import PipelinePreview from '../components/repository/PipelinePreview'
import RepositoryInput from '../components/repository/AnalyzeForm'

export default function LandingPage() {
  return (
    <div className="mx-auto grid w-full max-w-[var(--page-max-width)] gap-16 px-6 py-16 lg:grid-cols-2 lg:items-center lg:gap-12 lg:py-28">
      <div className="flex flex-col gap-6">
        <p className="text-eyebrow uppercase tracking-[0.14em] text-copper">
          Repository onboarding
        </p>
        <h1 className="font-ivy-presto text-heading-sm text-paper-white lg:text-heading-lg">
          The mentor that already knows the codebase.
        </h1>
        <p className="max-w-xl text-body-sm text-fog">
          RepoMentor reads a public GitHub repository, then explains its architecture, modules,
          and data flow, and answers questions with the source files to back every answer.
        </p>
        <div className="mt-2 max-w-xl">
          <RepositoryInput />
        </div>
      </div>

      <PipelinePreview />
    </div>
  )
}
