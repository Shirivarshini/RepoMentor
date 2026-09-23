import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import AnalyzeForm from '../components/repository/AnalyzeForm'
import { AskView, FilesView } from './RepositoryViews'
import RepositoryPage from './RepositoryPage'
import { repositoryApi } from '../services/repositoryApi'
import type { Repository } from '../types/repository'
vi.mock('../services/repositoryApi', () => ({repositoryApi: {analyze: vi.fn(), ask: vi.fn(), files: vi.fn(), status: vi.fn(), detail: vi.fn()}}))
const repo: Repository = {repository_id:'test', owner:'test', name:'project', url:'https://github.com/test/project', status:'COMPLETED', description:null, default_branch:'main', commit_sha:'abc123', error:null, qa_available:true, warnings:[], created_at:'', updated_at:'', analyzed_at:null, analysis_version:'1', languages:[], frameworks:[], summary:null, stats:null, important_modules:[], important_files:[], entry_points:[]}
function wrapper(children: ReactNode, path = '/') { return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><MemoryRouter initialEntries={[path]}>{children}</MemoryRouter></QueryClientProvider>) }
beforeEach(() => vi.clearAllMocks())
describe('Repository workflow', () => {
  it('submits URL and navigates to returned repository', async () => {
    vi.mocked(repositoryApi.analyze).mockResolvedValue({repository_id:'test', owner:'test', name:'project', url:repo.url, status:'QUEUED', message:''})
    wrapper(<Routes><Route path="/" element={<AnalyzeForm />} /><Route path="/repositories/test" element={<h1>Analysis page</h1>} /></Routes>)
    fireEvent.change(screen.getByLabelText('Public GitHub repository URL'), {target:{value:repo.url}})
    fireEvent.click(screen.getByRole('button', {name:'Analyze Repository'}))
    expect(await screen.findByText('Analysis page')).toBeInTheDocument()
    expect(repositoryApi.analyze).toHaveBeenCalledWith(repo.url)
  })
  it('shows API errors without rendering HTML', async () => {
    vi.mocked(repositoryApi.analyze).mockRejectedValue(new Error('<script>bad</script>'))
    wrapper(<AnalyzeForm />)
    fireEvent.change(screen.getByLabelText('Public GitHub repository URL'), {target:{value:repo.url}})
    fireEvent.click(screen.getByRole('button', {name:'Analyze Repository'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('<script>bad</script>')
    expect(document.querySelector('script')).toBeNull()
  })
  it('disables Q&A when embeddings are unavailable', () => {
    wrapper(<AskView repo={{...repo,qa_available:false}} />)
    expect(screen.getByLabelText('Your question')).toBeDisabled()
    expect(screen.getByRole('button', {name:'Ask RepoMentor'})).toBeDisabled()
  })
  it('renders a grounded answer and commit-pinned source', async () => {
    vi.mocked(repositoryApi.ask).mockResolvedValue({question_id:'q',answer_id:'a',question:'Where is run?',answer:'Defined in app.py.',explanation:null,interpretation:null,evidence:[],sources:[{file_path:'app.py',start_line:2,end_line:4,symbol:'run'}],confidence:.8,grounded:true,created_at:''})
    wrapper(<AskView repo={repo} />)
    fireEvent.change(screen.getByLabelText('Your question'), {target:{value:'Where is run?'}})
    fireEvent.click(screen.getByRole('button', {name:'Ask RepoMentor'}))
    expect(await screen.findByText('Defined in app.py.')).toBeInTheDocument()
    expect(screen.getByRole('link', {name:/app.py/})).toHaveAttribute('href', repo.url + '/blob/abc123/app.py#L2-L4')
  })
  it('selects file and exposes its symbols', async () => {
    vi.mocked(repositoryApi.files).mockResolvedValue({repository_id:'test',total:1,limit:500,offset:0,files:[{path:'src/app.py',language:'Python',size:30,purpose:null,is_important:true,is_entry_point:true,symbol_count:1,symbols:[{name:'run',symbol_type:'function',start_line:1,end_line:2,parent:null}]}]})
    wrapper(<FilesView repo={repo} />)
    fireEvent.click(await screen.findByRole('button', {name:/app.py/}))
    expect(screen.getByText('run')).toBeInTheDocument()
  })
  it('renders analysis progress', async () => {
    vi.mocked(repositoryApi.detail).mockResolvedValue({...repo,status:'ANALYZING'})
    vi.mocked(repositoryApi.status).mockResolvedValue({repository_id:'test',status:'ANALYZING',stage:'PARSING_CODE',progress:35,message:'Parsing code',error:null,updated_at:''})
    wrapper(<Routes><Route path="/repositories/:repositoryId" element={<RepositoryPage />} /></Routes>, '/repositories/test')
    await waitFor(() => expect(screen.getByRole('progressbar')).toHaveAttribute('value','35'))
  })
})
