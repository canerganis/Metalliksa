import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    optimizeDeps: {
      // Only the SPA is an entry point; bundled scientific docs are not apps.
      entries: ['index.html'],
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return undefined;
            if (/node_modules[\\/](three)[\\/]/.test(id)) return 'vendor-three';
            if (/node_modules[\\/](recharts|victory-vendor|d3-[^\\/]+)[\\/]/.test(id)) return 'vendor-charts';
            if (/node_modules[\\/](jspdf|jspdf-autotable|html2canvas|canvg|dompurify)[\\/]/.test(id)) return 'vendor-pdf';
            if (/node_modules[\\/][^\\/]*plotly[^\\/]*[\\/]/.test(id)) return 'vendor-plotly';
            if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return 'vendor-react';
            return undefined;
          },
        },
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {
        // Solver evidence and generated indexes must not reload an active UI job.
        ignored: [
          '**/graft/**',
          '**/.tmp-lpbf*/**',
          '**/.lpbf-*/**',
          '**/.warp-cache*/**',
          '**/docs/*.partial.json',
        ],
      },
    },
  };
});
