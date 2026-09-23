/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL. Empty (default) means same-origin; the dev server proxies /api and /health. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
