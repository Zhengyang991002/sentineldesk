import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend the dev and preview servers proxy to. Override with API_URL when it runs elsewhere.
const target = process.env.API_URL || 'http://localhost:8000'
const proxy = Object.fromEntries(['/triage', '/chat', '/tickets', '/health'].map((path) => [path, target]))

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
})
