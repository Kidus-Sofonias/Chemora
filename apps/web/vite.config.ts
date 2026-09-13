import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Chemora web — Vite configuration.
// Frontend environment configuration (VITE_*) is exposed through .env files:
//   VITE_API_BASE_URL      → Chemora FastAPI backend base URL
//   VITE_GOOGLE_CLIENT_ID  → public Google OAuth client id
// Frontend environment variables are NOT secrets.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  // CORS is configured server-side: the backend allows http://localhost:5173
  // (and :3000) origins with credentials (backend/app/core/config.py).
});