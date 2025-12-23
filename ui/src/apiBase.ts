const DEFAULT_API_BASE = '/api'

const normalizeBase = (base: string) => (base.endsWith('/') ? base.slice(0, -1) : base)

export const API_BASE = normalizeBase((import.meta.env.VITE_API_BASE_URL as string | undefined) || DEFAULT_API_BASE)

export const buildApiUrl = (path: string): string => {
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (path.startsWith('/api')) return `${API_BASE}${path.replace(/^\/api/, '') || ''}`
  if (path.startsWith('/')) return `${API_BASE}${path}`
  return `${API_BASE}/${path}`
}

export const installApiFetchShim = () => {
  const originalFetch = window.fetch.bind(window)
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string' && input.startsWith('/api')) {
      return originalFetch(buildApiUrl(input), init)
    }
    if (input instanceof URL && input.pathname.startsWith('/api')) {
      const rewritten = buildApiUrl(input.pathname + input.search + input.hash)
      return originalFetch(rewritten, init)
    }
    return originalFetch(input as any, init)
  }) as typeof fetch
}

export const createApiEventSource = (path: string): EventSource => new EventSource(buildApiUrl(path))
