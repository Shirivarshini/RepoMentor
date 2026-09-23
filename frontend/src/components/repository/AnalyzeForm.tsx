import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, LoaderCircle } from 'lucide-react'
import Button from '../ui/Button'
import { repositoryApi } from '../../services/repositoryApi'
export default function AnalyzeForm() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()
  const mutation = useMutation({ mutationFn: (value: string) => repositoryApi.analyze(value), onSuccess: data => { void navigate(`/repositories/${data.repository_id}`) } })
  function submit(event: FormEvent) { event.preventDefault(); mutation.mutate(url.trim()) }
  return <form onSubmit={submit} className="flex flex-col gap-3">
    <label htmlFor="repository-url" className="sr-only">Public GitHub repository URL</label>
    <input id="repository-url" type="url" required maxLength={200} value={url} onChange={e => setUrl(e.target.value)} disabled={mutation.isPending} aria-describedby="repository-url-note" placeholder="https://github.com/owner/repository" className="h-14 w-full rounded-pill border border-slate bg-carbon px-6 text-body-xs text-bone placeholder:text-fog" />
    <Button disabled={mutation.isPending} type="submit" className="self-start">{mutation.isPending ? <LoaderCircle size={16} className="spin" /> : <ArrowUpRight size={16} />}{mutation.isPending ? 'Connecting to GitHub…' : 'Analyze Repository'}</Button>
    <p id="repository-url-note" className="text-eyebrow text-fog">Public repositories · Source-linked answers · No code execution</p>
    {mutation.error && <p role="alert" className="error-message">{mutation.error.message}</p>}
  </form>
}
