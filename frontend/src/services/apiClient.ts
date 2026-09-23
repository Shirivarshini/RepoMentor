import axios from 'axios'
import { toApiError } from '../lib/errors'

/** Single Axios instance. All API errors are normalized into ApiError. */
export const apiClient = axios.create({
  // Empty by default: same-origin requests, proxied to the backend by the Vite dev server.
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 10_000,
  headers: { Accept: 'application/json' },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
)
