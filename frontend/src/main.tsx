import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import './styles.css'
import './public.css'

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: true } } })
const container = document.getElementById('root')!
const app = <React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>
const prerendered = container.dataset.prerendered
const pathname = window.location.pathname.replace(/\/$/, '') || '/'
if (prerendered === pathname && !window.location.search) ReactDOM.hydrateRoot(container, app)
else ReactDOM.createRoot(container).render(app)
