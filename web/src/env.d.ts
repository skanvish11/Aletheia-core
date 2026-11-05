/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `live` talks to the local backend; anything else (the default) replays bundled recordings. */
  readonly VITE_DATA_SOURCE?: string
  /** Path prefix for backend calls in live mode. Defaults to `/api`, proxied by the dev server. */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
