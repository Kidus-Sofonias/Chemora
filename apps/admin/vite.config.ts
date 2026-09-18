import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Chemora admin — Vite configuration.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
});
