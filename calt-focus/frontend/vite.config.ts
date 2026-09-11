import { defineConfig } from 'vite'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const srcRoot = path.join(repoRoot, 'src')

/**
 * Focus design host — http://127.0.0.1:5180/
 * Config lives under calt-focus/frontend/; app source stays in repo src/ (shared with Study shell).
 */
function caltDataMiddleware() {
  return {
    name: 'calt-data-middleware',
    configureServer(server) {
      const serveRoot = (urlPrefix, absDir) => {
        server.middlewares.use((req, res, next) => {
          const url = (req.url || '').split('?')[0]
          if (!url.startsWith(urlPrefix)) return next()
          const rel = decodeURIComponent(url.slice(urlPrefix.length) || '')
          if (!rel || rel.includes('..')) {
            res.statusCode = 400
            res.end('bad path')
            return
          }
          const file = path.resolve(absDir, rel)
          if (!file.startsWith(absDir + path.sep) && file !== absDir) {
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
      serveRoot('/calt-data/', path.join(repoRoot, 'data', 'productivity', 'behavior'))
      serveRoot('/calt-bible/', path.join(repoRoot, 'data', 'productivity', 'bible'))
    },
  }
}

function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        return path.resolve(srcRoot, 'assets', id.replace('figma:asset/', ''))
      }
    },
  }
}

export default defineConfig({
  root: repoRoot,
  publicDir: path.join(repoRoot, 'public'),
  server: {
    host: '127.0.0.1',
    port: 5180,
    strictPort: true,
    preTransformRequests: false,
    watch: {
      ignored: [
        '**/dist-focus/**',
        '**/dist/**',
        '**/data/**',
        '**/calt-focus/backend/**/build/**',
        '**/native/**',
        '**/.tmp*/**',
        '**/.pytest_cache/**',
        '**/.superpowers/**',
        '**/calt-focus/extensions/**',
        '**/node_modules/**',
      ],
    },
  },
  build: {
    outDir: path.join(repoRoot, 'dist-focus'),
    emptyOutDir: true,
  },
  optimizeDeps: {
    exclude: ['pyodide'],
    holdUntilCrawlEnd: false,
  },
  plugins: [figmaAssetResolver(), caltDataMiddleware(), react(), tailwindcss()],
  resolve: {
    alias: { '@': srcRoot },
  },
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
