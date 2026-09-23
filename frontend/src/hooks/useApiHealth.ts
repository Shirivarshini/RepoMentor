import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../services/healthApi'

/** Polls the API liveness endpoint. */
export function useApiHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: 1,
  })
}
