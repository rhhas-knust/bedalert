import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Four separate apps from one project: each page only loads its own code, so
// the public family app never ships the staff screens.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      input: {
        family: resolve(__dirname, 'index.html'),
        hospital: resolve(__dirname, 'hospital/index.html'),
        dispatch: resolve(__dirname, 'dispatch/index.html'),
        admin: resolve(__dirname, 'admin/index.html'),
      },
    },
  },
})
