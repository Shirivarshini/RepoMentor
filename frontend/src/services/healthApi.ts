import type { HealthResponse } from '../types/api'
import { apiClient } from './apiClient'

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}
