import { apiClient } from './apiClient'
import type { AnalyzeResult, AnalysisStatus, Repository, FilesResult, Architecture, Module, Flows, Setup, Answer } from '../types/repository'
const base = '/api/v1/repositories'
async function get<T>(id: string, path = '') { return (await apiClient.get<T>(`${base}/${id}${path}`)).data }
export const repositoryApi = {
  analyze: async (repository_url: string, force_reanalyze = false) => (await apiClient.post<AnalyzeResult>(`${base}/analyze`, { repository_url, force_reanalyze }, { timeout: 60_000 })).data,
  detail: (id: string) => get<Repository>(id),
  status: (id: string) => get<AnalysisStatus>(id, '/status'),
  files: (id: string, offset = 0) => get<FilesResult>(id, `/files?limit=500&offset=${offset}`),
  architecture: (id: string) => get<Architecture>(id, '/architecture'),
  modules: (id: string) => get<{repository_id: string; modules: Module[]}>(id, '/modules'),
  flows: (id: string) => get<Flows>(id, '/data-flow'),
  setup: (id: string) => get<Setup>(id, '/setup'),
  ask: async (id: string, question: string) => (await apiClient.post<Answer>(`${base}/${id}/ask`, { question }, { timeout: 180_000 })).data,
}
