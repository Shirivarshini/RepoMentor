import { useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Background, Controls, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { FileCode, Folder, Send, Sparkles, Search } from 'lucide-react'
import { repositoryApi } from '../services/repositoryApi'
import type { Answer, FileEntry, Repository, SetupItem } from '../types/repository'
import SourceLinks from '../components/repository/SourceLinks'
import { StateError } from './RepositoryPage'

function useView<T>(repo: Repository, name: string, query: () => Promise<T>) { return useQuery({ queryKey: ['view', repo.repository_id, name], queryFn: query }) }
const ref = (file_path: string) => ({ file_path, start_line: null, end_line: null, symbol: null })

export function ArchitectureView({ repo }: {repo: Repository}) {
  const query = useView(repo, 'architecture', () => repositoryApi.architecture(repo.repository_id))
  const [selected, setSelected] = useState<string | null>(null)
  if (query.error) return <StateError error={query.error} retry={() => { void query.refetch() }} />
  if (!query.data) return <p role="status">Loading architecture…</p>
  const graph = query.data
  return <section className="panel"><p className="eyebrow">A MAP OF THE CODEBASE</p><h2>See how it connects.</h2><p className="muted">{graph.summary}</p>
    <div className="architecture-canvas"><ReactFlow colorMode="dark" fitView nodesDraggable={false} nodesConnectable={false}
      nodes={graph.nodes.map((n, i) => ({ id: n.id, data: {label: `${n.label}${n.inferred ? ' (inferred)' : ''}`}, position: {x: (i % 3) * 280, y: Math.floor(i / 3) * 150}, style: {background: '#121317', borderColor: '#464853', color: '#e2e3e9', borderRadius: 10, padding: 20, width: 220} }))}
      edges={graph.edges.map(e => ({...e, label: `${e.label ?? ''}${e.inferred ? ' (inferred)' : ''}`, style: {stroke: '#cc9166', strokeDasharray: e.inferred ? '5 5' : undefined} }))}
      onNodeClick={(_, node) => setSelected(node.id)}><Background color="#2e3038" gap={24} /><Controls /></ReactFlow></div>
    <p className="small muted">Select a node to inspect its files. Dashed edges are inferred relationships.</p>
    {graph.nodes.filter(n => n.id === selected).map(n => <div className="node-details" key={n.id}><h3>{n.label}</h3><p>{n.description}</p><SourceLinks repo={repo} sources={n.files.map(ref)} /></div>)}
    <details><summary>Accessible graph outline</summary>{graph.nodes.map(n => <p key={n.id}>{n.label}: {n.description}</p>)}{graph.edges.map(e => <p key={e.id}>{e.source} → {e.target}: {e.label}{e.inferred && ' (inferred)'}</p>)}</details>
  </section>
}

export function ModulesView({ repo }: {repo: Repository}) {
  const query = useView(repo, 'modules', () => repositoryApi.modules(repo.repository_id))
  if (query.error) return <StateError error={query.error} retry={() => { void query.refetch() }} />
  if (!query.data) return <p role="status">Loading modules…</p>
  return <><p className="eyebrow">THE BUILDING BLOCKS</p><h2>Explore the modules.</h2><div className="module-grid">{query.data.modules.map(m => <article className="panel" key={m.id}><Folder size={20} className="copper" /><h3>{m.name}</h3><p className="muted">{m.purpose}</p><div className="tags"><span>{m.files.length} files</span><span>{m.symbol_count} symbols</span></div><details><summary>Browse files</summary><SourceLinks repo={repo} sources={m.files.map(ref)} /></details><p className="small muted">Imports: {m.depends_on.join(', ') || 'No resolved cross-module imports'}</p></article>)}</div></>
}

function FileTree({ files, choose, selected }: {files: FileEntry[]; choose: (file: FileEntry) => void; selected?: string}) {
  const groups = new Map<string, FileEntry[]>()
  for (const file of files) { const dir = file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : '/'; groups.set(dir, [...(groups.get(dir) ?? []), file]) }
  return <div className="file-tree">{[...groups].map(([dir, entries]) => <details key={dir} open><summary><Folder size={14} />{dir}</summary>{entries.map(file => <button key={file.path} className={selected === file.path ? 'selected' : ''} onClick={() => choose(file)}><FileCode size={14} /><span>{file.path.split('/').at(-1)}</span><span className="muted">{file.symbol_count}</span></button>)}</details>)}</div>
}

export function FilesView({ repo }: {repo: Repository}) {
  const [offset, setOffset] = useState(0), [search, setSearch] = useState(''), [selected, setSelected] = useState<FileEntry | null>(null)
  const query = useView(repo, `files-${offset}`, () => repositoryApi.files(repo.repository_id, offset))
  if (query.error) return <StateError error={query.error} retry={() => { void query.refetch() }} />
  if (!query.data) return <p role="status">Loading files…</p>
  const files = query.data.files.filter(f => f.path.toLowerCase().includes(search.toLowerCase()))
  return <><div className="section-heading"><div><p className="eyebrow">GO STRAIGHT TO THE SOURCE</p><h2>Inside the repository.</h2></div><label className="search-input"><Search size={16} /><input aria-label="Filter files on this page" placeholder="Find a file…" value={search} onChange={e => setSearch(e.target.value)} /></label></div>
    <div className="file-explorer panel"><aside><p className="small muted">{query.data.total} analyzed files</p><FileTree files={files} selected={selected?.path} choose={setSelected} />{!files.length && <p className="muted">No matching files.</p>}</aside><section className="file-detail">{selected ? <><p className="eyebrow">{selected.language ?? 'TEXT / CONFIGURATION'}</p><h3>{selected.path}</h3><p className="muted">{selected.purpose ?? 'No specific purpose established.'}</p><SourceLinks repo={repo} sources={[ref(selected.path)]} /><p className="small muted">{selected.size.toLocaleString()} bytes · {selected.symbol_count} symbols</p><h3>Symbols</h3>{selected.symbols.map((s, i) => <div className="symbol-row" key={`${s.name}-${i}`}><span className="tag">{s.symbol_type}</span><div><code>{s.parent ? `${s.parent}.` : ''}{s.name}</code><SourceLinks repo={repo} sources={[{file_path: selected.path, start_line: s.start_line, end_line: s.end_line, symbol: s.name}]} /></div></div>)}{!selected.symbols.length && <p className="muted">No symbols extracted. Open the source file to explore its contents.</p>}</> : <div className="empty-state"><FileCode size={36} /><h3>A good place to start.</h3><p className="muted">Select a file to explore its symbols and source references.</p></div>}</section></div>
    <div className="pagination"><button className="ghost-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 500))}>Previous</button><span>{offset + 1}–{Math.min(offset + 500, query.data.total)} of {query.data.total}</span><button className="ghost-button" disabled={offset + 500 >= query.data.total} onClick={() => setOffset(offset + 500)}>Next</button></div>
  </>
}

export function FlowsView({ repo }: {repo: Repository}) {
  const query = useView(repo, 'flows', () => repositoryApi.flows(repo.repository_id))
  if (query.error) return <StateError error={query.error} retry={() => { void query.refetch() }} />
  if (!query.data) return <p role="status">Loading flows…</p>
  return <><p className="eyebrow">FOLLOW THE CONNECTIONS</p><h2>Trace a path through the code.</h2>{query.data.message && <p className="muted">{query.data.message}</p>}{query.data.flows.map(flow => <section key={flow.id} className="panel"><h3>{flow.name}</h3><p className="muted">{flow.summary}</p><ol className="flow-steps">{flow.steps.map(step => <li key={step.order}><span className="flow-number">{step.order}</span><div><h3>{step.label}</h3><span className="tag">{step.inferred ? 'Inferred step' : 'Repository evidence'}</span>{step.file_path && <SourceLinks repo={repo} sources={[{...step, file_path: step.file_path}]} />}</div></li>)}</ol></section>)}</>
}

export function SetupView({ repo }: {repo: Repository}) {
  const query = useView(repo, 'setup', () => repositoryApi.setup(repo.repository_id))
  const [copied, setCopied] = useState('')
  if (query.error) return <StateError error={query.error} retry={() => { void query.refetch() }} />
  if (!query.data) return <p role="status">Loading setup guide…</p>
  const setup = query.data
  const sections: [string, SetupItem[]][] = [['Prerequisites', setup.prerequisites], ['Installation', setup.installation], ['Database setup', setup.database], ['Run the project', setup.run]]
  async function copy(text: string) { try { await navigator.clipboard.writeText(text); setCopied(text) } catch { setCopied('Clipboard unavailable; select and copy the command.') } }
  return <><p className="eyebrow">FROM READING TO RUNNING</p><h2>Your setup guide.</h2><p className="notice">Commands come from this repository. Review them before running; RepoMentor never executes them.</p>{sections.map(([title, items]) => <section className="panel" key={title}><h3>{title}</h3>{!items.length && <p className="muted">No documented instructions extracted for this section.</p>}{items.map((item, i) => <div className="setup-item" key={i}><h4>{item.title}</h4><p className="muted">{item.description}</p>{item.commands.length > 0 && <div className="code-block"><pre>{item.commands.join('\n')}</pre><button onClick={() => { void copy(item.commands.join('\n')) }}>{copied === item.commands.join('\n') ? 'Copied' : 'Copy'}</button></div>}<SourceLinks repo={repo} sources={item.sources} /></div>)}</section>)}<section className="panel"><h3>Environment variables</h3>{setup.environment_variables.map((v, i) => <div className="entry-row" key={`${v.name}-${i}`}><code>{v.name}</code><p className="muted">{v.description ?? 'Check the repository documentation for its value.'}</p>{v.source && <SourceLinks repo={repo} sources={[v.source]} />}</div>)}{!setup.environment_variables.length && <p className="muted">No environment example was found.</p>}</section><section className="panel"><h3>Common issues</h3>{setup.common_issues.map((item, i) => <div key={i}><h4>{item.issue}</h4><p>{item.resolution}</p><SourceLinks repo={repo} sources={item.sources} /></div>)}{!setup.common_issues.length && <p className="muted">No troubleshooting issues were extracted.</p>}</section><p className="small muted">{setup.message}</p></>
}

export function AskView({ repo }: {repo: Repository}) {
  const [question, setQuestion] = useState(''), [answers, setAnswers] = useState<Answer[]>([])
  const mutation = useMutation({ mutationFn: (text: string) => repositoryApi.ask(repo.repository_id, text), onSuccess: answer => { setAnswers(previous => [...previous, answer]); setQuestion('') } })
  function submit(event: FormEvent) { event.preventDefault(); if (question.trim().length >= 3) mutation.mutate(question.trim()) }
  const prompts = ['Where should I start reading?', 'Where are API routes defined?', 'How is the database connected?']
  const qaNotice = repo.warnings.find(warning => /embeddings? unavailable/i.test(warning))
    ?? 'Q&A is unavailable because embeddings could not be generated. Reanalyze this repository after resolving the provider issue.'
  return <div className="qa-layout"><section className="panel chat-panel"><p className="eyebrow">YOUR REPOSITORY MENTOR</p><h2>Ask the codebase.</h2><p className="muted">Get an explanation grounded in the files, with evidence you can inspect.</p>{!repo.qa_available && <p className="notice">{qaNotice}</p>}
    {!answers.length && <div className="question-prompts">{prompts.map(p => <button disabled={!repo.qa_available || mutation.isPending} key={p} onClick={() => setQuestion(p)}><Sparkles size={14} />{p}</button>)}</div>}
    <div aria-live="polite">{answers.map(a => <article className="conversation" key={a.answer_id}><div className="user-question"><span className="eyebrow">YOU</span><p>{a.question}</p></div><div className="mentor-answer"><span className="eyebrow">REPOMENTOR</span><p className="answer-text">{a.answer}</p>{a.explanation && <p className="answer-text muted">{a.explanation}</p>}{a.evidence.length > 0 && <details open><summary>Repository evidence</summary>{a.evidence.map((e, i) => <div className="evidence" key={i}><p>{e.statement}</p><SourceLinks repo={repo} sources={e.sources} /></div>)}</details>}{a.interpretation && <div className="notice"><strong>Interpretation</strong><p>{a.interpretation}</p></div>}<SourceLinks repo={repo} sources={a.sources} /><p className="small muted">{a.grounded ? `Grounding score ${Math.round(a.confidence * 100)}% · Retrieval heuristic, not a correctness probability` : 'Insufficient repository evidence'}</p></div></article>)}{mutation.isPending && <p role="status">Reading the relevant sources…</p>}</div>
    {mutation.error && <p role="alert" className="error-message">{mutation.error.message}</p>}
    <form className="question-form" onSubmit={submit}><label htmlFor="question">Your question</label><textarea id="question" value={question} onChange={e => setQuestion(e.target.value)} minLength={3} maxLength={1000} required disabled={!repo.qa_available || mutation.isPending} placeholder="How does this project work?" rows={3} /><div><span className="small muted">{question.length}/1000</span><button className="primary-button" disabled={!repo.qa_available || mutation.isPending || question.trim().length < 3}><Send size={15} />{mutation.isPending ? 'Thinking…' : 'Ask RepoMentor'}</button></div></form>
  </section><aside className="panel qa-aside"><h3>Answers you can trace.</h3><p className="muted">Every source link opens the exact analyzed commit on GitHub.</p><hr /><p className="muted">Evidence and interpretation are shown separately. If the sources don’t support an answer, RepoMentor says so.</p><hr /><p className="small muted">Each question is answered independently. Conversation history is kept for this view only.</p></aside></div>
}
