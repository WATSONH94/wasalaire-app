import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Domaine/API configurables : en prod le front est servi SAME-ORIGIN (API base relative,
// aucune URL codée en dur). En dev, on proxifie /v1, /health et /assets vers l'API locale.
export default defineConfig({
  plugins: [
    react(),
    // Service worker en AUTO-DESTRUCTION : le SW déployé se désinscrit et vide tous les
    // caches chez CHAQUE visiteur (y compris ceux coincés sur une ancienne version en cache).
    // Un SaaS de paie n'a pas besoin de mode hors-ligne ; la fiabilité prime sur l'installabilité.
    // (Les anciens SW periment la console → « rien ne fonctionne ». Cette option les tue proprement.)
    VitePWA({
      selfDestroying: true,
      registerType: 'autoUpdate',
    }),
  ],
  server: {
    proxy: {
      // Backend API locale (dev). Port surchargé par VITE_API_PORT si besoin (défaut 8000).
      '/v1': `http://localhost:${process.env.VITE_API_PORT ?? 8000}`,
      '/health': `http://localhost:${process.env.VITE_API_PORT ?? 8000}`,
      '/assets': `http://localhost:${process.env.VITE_API_PORT ?? 8000}`,
    },
  },
})
