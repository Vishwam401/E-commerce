import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from './App'

export { getMetadata, publicPages, siteOrigin } from './metadata'

export function render(path: string) {
  const client = new QueryClient()
  return renderToString(<QueryClientProvider client={client}><StaticRouter location={path}><App /></StaticRouter></QueryClientProvider>)
}
