import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import AdminApp from './admin/AdminApp.tsx'
import { AuthProvider } from './auth'
import { isAdminSurface } from './surface'

const Surface = isAdminSurface() ? AdminApp : App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Surface />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
