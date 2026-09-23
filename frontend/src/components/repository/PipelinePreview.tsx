const STEPS = [
  { name: 'Collect', detail: 'Repository metadata, file tree, and relevant sources' },
  { name: 'Analyze', detail: 'Languages, frameworks, entry points, important modules' },
  { name: 'Parse', detail: 'Functions, classes, imports, and routes with line ranges' },
  { name: 'Chunk + embed', detail: 'Logical code chunks stored for semantic search' },
  { name: 'Retrieve', detail: 'The code most relevant to your question' },
  { name: 'Explain', detail: 'Answers grounded in cited source files' },
] as const

/** Static description of how RepoMentor reads a repository. */
export default function PipelinePreview() {
  return (
    <section
      aria-labelledby="pipeline-heading"
      className="rounded-card border border-graphite bg-onyx p-6"
    >
      <h2 id="pipeline-heading" className="text-eyebrow uppercase tracking-[0.14em] text-copper">
        How RepoMentor reads a repository
      </h2>
      <ol className="mt-6 flex flex-col">
        {STEPS.map((step, index) => (
          <li
            key={step.name}
            className="flex items-baseline gap-4 border-t border-graphite py-4 first:border-t-0 first:pt-0 last:pb-0"
          >
            <span className="w-6 shrink-0 text-eyebrow text-steel">
              {String(index + 1).padStart(2, '0')}
            </span>
            <div>
              <p className="text-body-xs font-medium text-paper-white">{step.name}</p>
              <p className="text-body-xs text-fog">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
