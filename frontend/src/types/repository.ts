export interface Source { file_path: string; start_line: number | null; end_line: number | null; symbol: string | null }
export interface AnalysisStatus { repository_id: string; status: string; stage: string | null; progress: number; message: string; error: {code: string; message: string} | null; updated_at: string }
export interface AnalyzeResult { repository_id: string; owner: string; name: string; url: string; status: string; message: string }
export interface Module { id: string; name: string; purpose: string; files: string[]; symbol_count: number; depends_on: string[] }
export interface Repository {
  repository_id: string; owner: string; name: string; url: string; description: string | null
  default_branch: string | null; commit_sha: string | null; status: string; qa_available: boolean
  error: {code: string; message: string} | null; warnings: string[]; created_at: string; updated_at: string
  analyzed_at: string | null; analysis_version: string | null
  languages: {name: string; file_count: number; percentage: number}[]
  frameworks: {name: string; category: string; evidence: Source[]}[]
  summary: {purpose: string; architecture_summary: string; technologies: string[]; source: string} | null
  stats: {files_analyzed: number; files_skipped: number; languages_detected: number; modules_found: number; entry_points_found: number; symbols_found: number; chunks_created: number; truncated: boolean} | null
  important_modules: Pick<Module, 'id' | 'name' | 'purpose'>[]
  important_files: {path: string; language: string | null; reason: string}[]
  entry_points: {file_path: string; kind: string; symbol: string | null; reason: string}[]
}
export interface FileEntry { path: string; language: string | null; size: number; purpose: string | null; is_important: boolean; is_entry_point: boolean; symbol_count: number; symbols: {name: string; symbol_type: string; start_line: number; end_line: number; parent: string | null}[] }
export interface FilesResult { repository_id: string; total: number; limit: number; offset: number; files: FileEntry[] }
export interface Architecture { repository_id: string; summary: string; generated_at: string; nodes: {id: string; label: string; type: string; description: string; files: string[]; inferred: boolean}[]; edges: {id: string; source: string; target: string; label: string | null; inferred: boolean}[] }
export interface Flows { repository_id: string; message: string | null; flows: {id: string; name: string; summary: string; steps: {order: number; label: string; kind: string; file_path: string | null; symbol: string | null; start_line: number | null; end_line: number | null; inferred: boolean}[]}[] }
export interface SetupItem { title: string; description: string | null; commands: string[]; sources: Source[] }
export interface Setup { repository_id: string; prerequisites: SetupItem[]; installation: SetupItem[]; database: SetupItem[]; run: SetupItem[]; environment_variables: {name: string; description: string | null; required: boolean | null; default: string | null; source: Source | null}[]; common_issues: {issue: string; resolution: string; sources: Source[]}[]; message: string | null }
export interface Answer { question_id: string; answer_id: string; question: string; answer: string; explanation: string | null; evidence: {statement: string; sources: Source[]}[]; interpretation: string | null; sources: Source[]; confidence: number; grounded: boolean; created_at: string }
