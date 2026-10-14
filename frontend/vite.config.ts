import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Domaine/API configurables : en prod le front est servi SAME-ORIGIN (API base relative,
// aucune URL codée en dur). En dev, on proxifie /v1, /health et /assets vers l'API locale.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'WaSalaire',
        short_name: 'WaSalaire',
        description: 'La paie simplifiée et conforme au Bénin.',
        lang: 'fr',
        theme_color: '#1E2A78',
        background_color: '#F8FAFC',
        display: 'standalone',
        start_url: '/',
      },
    }),
  ],
  server: {
    proxy: {
      '/v1': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/assets': 'http://localhost:8000',
    },
  },
})
