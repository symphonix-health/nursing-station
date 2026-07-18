import './styles/design-system.css'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

type Theme = 'light' | 'dark' | 'system'
const saved = (localStorage.getItem('theme') as Theme | null) ?? 'system'
const resolved = saved === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : saved
document.documentElement.dataset.theme = resolved

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>,
)
