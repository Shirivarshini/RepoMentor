import axios from 'axios'
import type { ErrorEnvelope } from '../types/api'

/** Error codes produced by the client itself (not by the API). */
export type ClientErrorCode = 'NETWORK_ERROR' | 'UNKNOWN_ERROR'

/** Normalized error thrown by the API client. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number | null
  readonly details: Record<string, unknown>
  readonly requestId: string | null

  constructor(init: {
    code: string
    message: string
    status?: number | null
    details?: Record<string, unknown>
    requestId?: string | null
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.code = init.code
    this.status = init.status ?? null
    this.details = init.details ?? {}
    this.requestId = init.requestId ?? null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Runtime check that a response body is the contract's error envelope. */
function parseEnvelope(data: unknown): ErrorEnvelope | null {
  if (!isRecord(data) || !isRecord(data.error)) return null
  const { code, message, details, request_id } = data.error
  if (typeof code !== 'string' || typeof message !== 'string') return null
  return {
    error: {
      code,
      message,
      details: isRecord(details) ? details : {},
      request_id: typeof request_id === 'string' ? request_id : '',
    },
  }
}

/** Convert anything thrown by a request into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? null
    const envelope = parseEnvelope(error.response?.data)
    if (envelope) {
      return new ApiError({
        code: envelope.error.code,
        message: envelope.error.message,
        status,
        details: envelope.error.details,
        requestId: envelope.error.request_id || null,
      })
    }
    if (!error.response) {
      return new ApiError({
        code: 'NETWORK_ERROR',
        message: 'Could not reach the RepoMentor API.',
      })
    }
    return new ApiError({
      code: 'UNKNOWN_ERROR',
      message: 'The API returned an unexpected response.',
      status,
    })
  }

  return new ApiError({
    code: 'UNKNOWN_ERROR',
    message: error instanceof Error ? error.message : 'An unknown error occurred.',
  })
}
