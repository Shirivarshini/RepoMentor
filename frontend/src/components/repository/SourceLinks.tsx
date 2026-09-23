import type { Repository, Source } from '../../types/repository'
export default function SourceLinks({ sources, repo }: { sources: Source[]; repo: Repository }) {
  return <div className="source-links">{sources.map((source, i) => {
    const href = `${repo.url}/blob/${encodeURIComponent(repo.commit_sha ?? repo.default_branch ?? 'HEAD')}/${source.file_path.split('/').map(encodeURIComponent).join('/')}${source.start_line ? `#L${source.start_line}${source.end_line ? `-L${source.end_line}` : ''}` : ''}`
    return <a key={`${source.file_path}-${i}`} href={href} target="_blank" rel="noopener noreferrer">{source.file_path}{source.start_line ? `:${source.start_line}${source.end_line !== source.start_line ? `–${source.end_line}` : ''}` : ''} ↗</a>
  })}</div>
}
