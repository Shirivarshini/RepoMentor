/**
 * Types mirroring API_CONTRACT.md (the canonical contract).
 * Change these only when the contract changes.
 */

/** GET /health */
export interface HealthResponse {
  status: 'ok'
}

/** Error codes defined by the contract. Clients must tolerate unknown codes. */
export type KnownErrorCode =
  | 'VALIDATION_ERROR'
  | 'REPOSITORY_NOT_FOUND'
  | 'NOT_FOUND'
  | 'ANALYSIS_NOT_READY'
  | 'RATE_LIMIT_EXCEEDED'
  | 'GITHUB_RATE_LIMIT'
  | 'GITHUB_API_ERROR'
  | 'AI_PROVIDER_ERROR'
  | 'EMBEDDING_ERROR'
  | 'DATABASE_ERROR'
  | 'INTERNAL_ERROR'
  | 'ANALYSIS_FAILED'
  | 'REPOSITORY_TOO_LARGE'
  | 'EMPTY_REPOSITORY'
  | 'UNSUPPORTED_REPOSITORY'

/** Standard error envelope. */
export interface ErrorEnvelope {
  error: {
    /** Usually a KnownErrorCode; typed as string so unknown codes are handled gracefully. */
    code: string
    message: string
    details: Record<string, unknown>
    request_id: string
  }
}
