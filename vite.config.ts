import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'


function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        const filename = id.replace('figma:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

export default defineConfig({
  server: {
    // 127.0.0.1 only — host:true (0.0.0.0) hangs on some Windows setups (ERR_CONNECTION_RESET)
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // Pre-transform entry files at startup (helps dev mode on slow Windows cold starts)
    warmup: {
      clientFiles: ['./index.html', './src/main.tsx', './src/app/App.tsx'],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 5173,
  },
  plugins: [
    figmaAssetResolver(),
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Pyodide is loaded from CDN at runtime — keep npm package out of the browser graph
  optimizeDeps: {
    exclude: ['pyodide'],
  },
  build: {
    rollupOptions: {
      external: ['pyodide'],
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
