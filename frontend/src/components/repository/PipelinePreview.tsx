import { useState } from 'react'
import { Braces, CircleCheck, FileCode2, GitBranch, Network } from 'lucide-react'

const previews = {
  overview: <><div className="preview-stats"><span><strong>219</strong> files</span><span><strong>7</strong> modules</span><span><strong>4</strong> entry points</span></div><div className="preview-summary"><p>WHAT THIS REPOSITORY APPEARS TO BE</p><strong>A structured web application with clear service boundaries.</strong></div></>,
  architecture: <div className="mini-architecture"><span>frontend</span><i /><span>api</span><i /><span>service</span><i /><span>data</span></div>,
  sources: <div className="preview-source"><FileCode2 size={17} /><div><code>app/routes.py</code><small>lines 24–58 · create_app()</small></div><CircleCheck size={16} /></div>,
}

export default function PipelinePreview() {
  const [view, setView] = useState<keyof typeof previews>('overview')
  return <section className="product-preview" aria-label="RepoMentor product preview">
    <div className="preview-topline"><span><GitBranch size={14} /> pallets / flask</span><span className="preview-status"><i /> ANALYZING</span></div>
    <div className="preview-tabs" role="tablist" aria-label="Preview sections">
      {(['overview', 'architecture', 'sources'] as const).map(item => <button key={item} role="tab" aria-selected={view === item} onClick={() => setView(item)}>{item === 'architecture' && <Network size={13} />}{item === 'sources' && <Braces size={13} />}{item}</button>)}
    </div>
    <div className="preview-content">{previews[view]}</div>
    <div className="preview-footer"><span>Repository evidence</span><span>Read-only analysis</span></div>
  </section>
}
