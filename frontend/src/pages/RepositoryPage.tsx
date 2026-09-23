import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'
import { ArrowUpRight, BookOpen, CheckCircle2, FileSearch, FolderTree, GitBranch, Layers, LayoutDashboard, Menu, MessageSquare, Network, RefreshCw, Route, Search, X } from 'lucide-react'
import { repositoryApi } from '../services/repositoryApi'
import type { Repository } from '../types/repository'
import SourceLinks from '../components/repository/SourceLinks'
import { ArchitectureView, FilesView, FlowsView, ModulesView, SetupView, AskView } from './RepositoryViews'

const tabs = [
  ['overview', 'Overview', LayoutDashboard], ['architecture', 'Architecture', Network],
  ['modules', 'Modules', Layers], ['files', 'Files', FolderTree], ['data-flow', 'Data Flow', Route],
  ['setup', 'Setup', BookOpen], ['ask', 'Ask', MessageSquare],
] as const

export default function RepositoryPage() {
  const { repositoryId = '', section = 'overview' } = useParams()
  const navigate = useNavigate()
  const client = useQueryClient()
  const [navOpen, setNavOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const status = useQuery({ queryKey: ['status', repositoryId], queryFn: () => repositoryApi.status(repositoryId), refetchInterval: query => ['QUEUED', 'ANALYZING'].includes(query.state.data?.status ?? '') ? 2000 : false })
  const detail = useQuery({ queryKey: ['repository', repositoryId, status.data?.status], queryFn: () => repositoryApi.detail(repositoryId) })
  const retry = useMutation({ mutationFn: () => repositoryApi.analyze(detail.data!.url, true), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['status', repositoryId] }); await client.invalidateQueries({ queryKey: ['repository', repositoryId] }); await client.invalidateQueries({ queryKey: ['view', repositoryId] }) } })

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen(true) }
      if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes((event.target as HTMLElement)?.tagName)) { event.preventDefault(); setPaletteOpen(true) }
      if (event.key === 'Escape') { setPaletteOpen(false); setNavOpen(false) }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  const error = detail.error || status.error
  if (error) return <div className="dashboard"><StateError error={error} retry={() => { void status.refetch(); void detail.refetch() }} /></div>
  if (!detail.data || !status.data) return <WorkspaceSkeleton />
  const repo = detail.data
  const current = status.data
  const completed = current.status === 'COMPLETED'
  const active = tabs.find(([path]) => path === section)?.[1] ?? 'Overview'

  return <div className="repository-workspace">
    <header className="workspace-topbar">
      <button className="icon-button mobile-nav-trigger" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={19} /></button>
      <Link to="/" className="workspace-brand">RepoMentor</Link>
      <span className="workspace-repo"><GitBranch size={14} />{repo.owner} / {repo.name}</span>
      <span className={`status-badge ${current.status.toLowerCase()}`}><StatusIcon status={current.status} />{current.status}</span>
      <div className="topbar-actions"><button className="ghost-button compact" disabled={retry.isPending || ['QUEUED', 'ANALYZING'].includes(current.status)} onClick={() => retry.mutate()}><RefreshCw size={14} />{retry.isPending ? 'Queuing…' : 'Reanalyze'}</button><a className="ghost-button compact" href={repo.url} target="_blank" rel="noopener noreferrer">GitHub <ArrowUpRight size={14} /></a></div>
    </header>
    <aside className={`workspace-sidebar ${navOpen ? 'open' : ''}`} aria-label="Repository navigation">
      <div className="sidebar-mobile-head"><strong>Repository sections</strong><button className="icon-button" aria-label="Close navigation" onClick={() => setNavOpen(false)}><X size={18} /></button></div>
      <nav>{tabs.map(([path, label, Icon]) => <NavLink key={path} to={`/repositories/${repositoryId}/${path}`} onClick={() => setNavOpen(false)} className={() => section === path ? 'active' : ''}><Icon size={17} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-analysis"><span className="eyebrow">ANALYSIS</span><p><StatusIcon status={current.status} />{current.status === 'COMPLETED' ? 'Completed' : current.message}</p><small>{completed && repo.analyzed_at ? `Updated ${formatRelative(repo.analyzed_at)}` : `${current.progress}% complete`}</small></div>
      <button className="sidebar-search" onClick={() => setPaletteOpen(true)}><Search size={16} />Search workspace <kbd>⌘ K</kbd></button>
    </aside>
    {navOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    <main className="workspace-main">
      <div className="workspace-heading"><div><p className="eyebrow">{active}</p><h1>{repo.name}</h1><p className="muted">{repo.description || `${repo.owner} / ${repo.name}`}</p><div className="tags">{repo.frameworks.map(item => <span key={item.name}>{item.name}</span>)}{repo.languages.slice(0, 3).map(item => <span key={item.name}>{item.name}</span>)}</div></div><div className="workspace-meta"><code>{repo.commit_sha?.slice(0, 8) ?? repo.default_branch ?? 'No commit'}</code><span>{completed ? 'Repository snapshot ready' : current.message}</span></div></div>
      {retry.error && <p role="alert" className="error-message">{retry.error.message}</p>}
      {current.status === 'FAILED' ? <section className="panel"><h2>Analysis could not finish</h2><p role="alert" className="error-message">{current.error?.message}</p><p className="muted">Use Reanalyze to retry this repository.</p></section> : !completed ? <AnalysisProgress current={current} /> : <>
        {repo.warnings.length > 0 && <details className="notice"><summary>{repo.warnings.length} analysis {repo.warnings.length === 1 ? 'notice' : 'notices'}</summary>{repo.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</details>}
        <div className="view-content" key={section}>{section === 'overview' ? <Overview repo={repo} /> : section === 'architecture' ? <ArchitectureView repo={repo} /> : section === 'modules' ? <ModulesView repo={repo} /> : section === 'files' ? <FilesView repo={repo} /> : section === 'data-flow' ? <FlowsView repo={repo} /> : section === 'setup' ? <SetupView repo={repo} /> : <AskView repo={repo} />}</div>
      </>}
    </main>
    {paletteOpen && <QuickNavigation repo={repo} close={() => setPaletteOpen(false)} navigate={path => { setPaletteOpen(false); void navigate(path) }} reanalyze={() => { setPaletteOpen(false); retry.mutate() }} />}
  </div>
}

function Overview({ repo }: { repo: Repository }) {
  const [expanded, setExpanded] = useState(false)
  const stats = [
    ['Files', repo.stats?.files_analyzed, 'files'], ['Modules', repo.stats?.modules_found, 'modules'],
    ['Entry points', repo.stats?.entry_points_found, 'files'], ['Code chunks', repo.stats?.chunks_created, 'ask'],
  ] as const
  return <>
    <div className="interactive-stats">{stats.map(([label, value, target]) => <Link key={label} className="stat-card" to={`/repositories/${repo.repository_id}/${target}`}><strong>{value ?? '—'}</strong><span>{label}</span><ArrowUpRight size={15} /></Link>)}</div>
    <section className="summary-card"><p className="eyebrow">WHAT THIS REPOSITORY APPEARS TO BE</p><h2>{repo.summary?.purpose || 'A repository waiting for analysis.'}</h2><p>{repo.summary?.architecture_summary}</p><div className="summary-disclosure"><div><span className="eyebrow">EVIDENCE</span><p>Languages, dependency files, symbols, and imports found in this snapshot.</p></div><div><span className="eyebrow">INTERPRETATION</span><p>Structure is inferred from repository evidence and marked where execution order is not proven.</p></div></div></section>
    <div className="overview-grid"><section className="panel"><p className="eyebrow">LANGUAGE COMPOSITION</p><h2>What it’s built with.</h2>{repo.languages.map(language => <div className="language-row" key={language.name}><div><span>{language.name}</span><span>{language.percentage}%</span></div><meter min={0} max={100} value={language.percentage} aria-label={`${language.name} share`} /></div>)}{!repo.languages.length && <p className="muted">No supported source languages detected.</p>}</section><section className="panel ask-invite"><MessageSquare size={24} /><p className="eyebrow">INVESTIGATE FURTHER</p><h2>Follow your curiosity.</h2><p className="muted">Ask about a feature, find a function, or work out where to start. Answers link back to repository evidence.</p><Link className="ghost-button" to={`/repositories/${repo.repository_id}/ask`}>Ask RepoMentor <ArrowUpRight size={14} /></Link></section></div>
    <section className="panel start-here"><div className="section-heading"><div><p className="eyebrow">START HERE</p><h2>Your first files to read.</h2></div><Link className="text-link" to={`/repositories/${repo.repository_id}/files`}>Explore files <ArrowUpRight size={14} /></Link></div>{(expanded ? repo.important_files : repo.important_files.slice(0, 5)).map((file, index) => <div className="reading-row" key={file.path}><span className="reading-number">{String(index + 1).padStart(2, '0')}</span><div><SourceLinks repo={repo} sources={[{ file_path: file.path, start_line: null, end_line: null, symbol: null }]} /><p className="muted small">{file.reason}</p></div><span className="tag">{file.language ?? 'Documentation'}</span></div>)}{!repo.important_files.length && <p className="muted">No conventional entry or dependency files were detected.</p>}{repo.important_files.length > 5 && <button className="ghost-button compact" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer' : 'Show all recommended files'}</button>}</section>
  </>
}

function AnalysisProgress({ current }: { current: { status: string; stage: string | null; progress: number; message: string } }) {
  const stages = ['Fetching repository', 'Analyzing structure', 'Parsing code', 'Chunking', 'Embedding', 'Generating insights', 'Finalizing']
  return <section className="panel analysis-progress" aria-live="polite"><p className="eyebrow">GETTING TO KNOW YOUR REPOSITORY</p><h2>{current.message}</h2><p className="muted">Fetching sources, mapping structure, and preparing repository evidence. You can keep this page open.</p><progress max={100} value={current.progress} aria-label="Analysis progress" /><span>{current.progress}% complete</span><ol className="pipeline-stages">{stages.map(label => <li key={label} className={current.stage === label.toUpperCase().replaceAll(' ', '_') ? 'active' : ''}>{label}</li>)}</ol></section>
}

function QuickNavigation({ repo, close, navigate, reanalyze }: { repo: Repository; close: () => void; navigate: (path: string) => void; reanalyze: () => void }) {
  const actions = [
    ['Go to Overview', 'overview', LayoutDashboard], ['Open Architecture', 'architecture', Network], ['Search Files', 'files', FileSearch], ['Ask RepoMentor', 'ask', MessageSquare],
  ] as const
  return <div className="command-layer" role="dialog" aria-modal="true" aria-label="Quick navigation"><button className="command-backdrop" aria-label="Close quick navigation" onClick={close} /><div className="command-palette"><div><Search size={18} /><input autoFocus placeholder="Search navigation…" aria-label="Search navigation" /></div>{actions.map(([label, path, Icon]) => <button key={path} onClick={() => navigate(`/repositories/${repo.repository_id}/${path}`)}><Icon size={17} />{label}<kbd>↵</kbd></button>)}<button onClick={reanalyze}><RefreshCw size={17} />Reanalyze repository</button><a href={repo.url} target="_blank" rel="noopener noreferrer"><GitBranch size={17} />Open GitHub repository <ArrowUpRight size={15} /></a><p>Press Esc to close · Press / to open</p></div></div>
}

function StatusIcon({ status }: { status: string }) { return status === 'COMPLETED' ? <CheckCircle2 size={14} /> : <span className="status-dot" aria-hidden="true" /> }
function formatRelative(value: string) { const seconds = Math.max(0, Math.round((Date.now() - Date.parse(value)) / 1000)); return seconds < 60 ? 'just now' : seconds < 3600 ? `${Math.floor(seconds / 60)}m ago` : `${Math.floor(seconds / 3600)}h ago` }
export function StateError({ error, retry }: { error: Error; retry: () => void }) { return <div className="panel"><p role="alert" className="error-message">{error.message}</p><button className="ghost-button" onClick={retry}>Try again</button></div> }
function WorkspaceSkeleton() { return <div className="repository-workspace skeleton-workspace"><div className="skeleton-top" /><div className="skeleton-side" /><main className="workspace-main"><div className="skeleton-line wide" /><div className="skeleton-line" /><div className="skeleton-cards"><i /><i /><i /><i /></div><div className="skeleton-panel" /></main></div> }
