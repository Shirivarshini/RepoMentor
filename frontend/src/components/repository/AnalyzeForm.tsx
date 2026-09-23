import { useMemo, useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, CheckCircle2, LoaderCircle } from 'lucide-react'
import Button from '../ui/Button'
import { repositoryApi } from '../../services/repositoryApi'

const publicRepository = /^https:\/\/github\.com\/[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9_.-]+\/?$/

export default function AnalyzeForm() {
  const [url, setUrl] = useState('')
  const [touched, setTouched] = useState(false)
  const navigate = useNavigate()
  const isValid = useMemo(() => publicRepository.test(url.trim()), [url])
  const mutation = useMutation({
    mutationFn: (value: string) => repositoryApi.analyze(value),
    onSuccess: data => { void navigate(`/repositories/${data.repository_id}`) },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (isValid) mutation.mutate(url.trim())
  }

  const feedback = mutation.error
    ? mutation.error.message
    : touched && url && !isValid
      ? 'Enter a public GitHub URL in the form github.com/owner/repository.'
      : null

  return <form onSubmit={submit} className="analyze-form" noValidate>
    <label htmlFor="repository-url" className="sr-only">Public GitHub repository URL</label>
    <div className={`repository-field ${touched && url ? (isValid ? 'valid' : 'invalid') : ''}`}>
      <input id="repository-url" type="url" maxLength={200} value={url}
        onBlur={() => setTouched(true)} onChange={event => setUrl(event.target.value)}
        disabled={mutation.isPending} aria-describedby="repository-url-note repository-url-feedback"
        aria-invalid={Boolean(feedback)} placeholder="github.com/owner/repository" />
      {touched && isValid && <CheckCircle2 className="field-status" size={18} aria-label="Valid GitHub repository URL" />}
    </div>
    <Button disabled={mutation.isPending} type="submit" className="analyze-button">
      {mutation.isPending ? <LoaderCircle size={16} className="spin" /> : <ArrowUpRight size={16} />}
      {mutation.isPending ? 'Starting analysis…' : 'Analyze Repository'}
    </Button>
    <p id="repository-url-note" className="trust-note">Public repositories only <span>·</span> RepoMentor never executes repository code</p>
    {feedback && <p id="repository-url-feedback" role="alert" className="error-message">{feedback}</p>}
  </form>
}
