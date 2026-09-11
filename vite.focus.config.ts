import { defineConfig } from 'vite'
import path from 'path'
import fs from 'fs'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

/**
 * Focus design host — http://127.0.0.1:5180/
 * Separate from Study :5173 and Focus static :5174.
 */
function caltDataMiddleware() {
  return {
    name: 'calt-data-middleware',
    configureServer(server) {
      const serveRoot = (urlPrefix, dirParts) => {
        server.middlewares.use((req, res, next) => {
          const url = (req.url || '').split('?')[0]
          if (!url.startsWith(urlPrefix)) return next()
          const rel = decodeURIComponent(url.slice(urlPrefix.length) || '')
          if (!rel || rel.includes('..')) {
            res.statusCode = 400
            res.end('bad path')
            return
          }
          const root = path.resolve(__dirname, ...dirParts)
          const file = path.resolve(root, rel)
          if (!file.startsWith(root + path.sep) && file !== root) {
            res.statusCode = 400
            res.end('bad path')
            return
          }
          fs.readFile(file, (err, buf) => {
            if (err) {
              res.statusCode = 404
              res.end('missing')
              return
            }
            const ct = file.endsWith('.json')
              ? 'application/json; charset=utf-8'
              : 'application/octet-stream'
            res.setHeader('Content-Type', ct)
            res.setHeader('Cache-Control', file.includes('structured') ? 'public, max-age=3600' : 'no-store')
            res.end(buf)
          })
        })
      }
      serveRoot('/calt-data/', ['data', 'productivity', 'behavior'])
      serveRoot('/calt-bible/', ['data', 'productivity', 'bible'])
    },
  }
}

function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        return path.resolve(__dirname, 'src/assets', id.replace('figma:asset/', ''))
      }
    },
  }
}

export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 5180,
    strictPort: true,
    preTransformRequests: false,
    watch: {
      // Huge trees (dist-focus, data locks, native) freeze Vite's event loop on Windows
      ignored: [
        '**/dist-focus/**',
        '**/dist/**',
        '**/data/**',
        '**/native/**',
        '**/.tmp*/**',
        '**/.pytest_cache/**',
        '**/.superpowers/**',
        '**/calt-gate-extension/**',
        '**/selftracker-extension/**',
        '**/node_modules/**',
      ],
    },
  },
  optimizeDeps: {
    exclude: ['pyodide'],
    holdUntilCrawlEnd: false,
  },
  plugins: [figmaAssetResolver(), caltDataMiddleware(), react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
