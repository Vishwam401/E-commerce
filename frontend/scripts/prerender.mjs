import { readFile, writeFile } from 'node:fs/promises'
import { URL } from 'node:url'
import { getMetadata, render, publicPages, siteOrigin } from '../node_modules/.tmp/alpha-prerender/prerender.js'

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character])
}

const template = await readFile('dist/index.html', 'utf8')
const paths = Object.keys(publicPages)
function html(path, markup) {
  const { title, description, index } = getMetadata(path)
  const canonical = new URL(path, siteOrigin).href
  return template
    .replace(/<title>.*?<\/title>/, `<title>${escapeHtml(title)}</title>`)
    .replace(/(<meta name="description" content=")[^"]*/, `$1${escapeHtml(description)}`)
    .replace(/(<meta property="og:title" content=")[^"]*/, `$1${escapeHtml(title)}`)
    .replace(/(<meta property="og:description" content=")[^"]*/, `$1${escapeHtml(description)}`)
    .replace(/(<meta property="og:url" content=")[^"]*/, `$1${canonical}`)
    .replace(/(<meta name="robots" content=")[^"]*/, `$1${index ? 'index,follow' : 'noindex,follow'}`)
    .replace(/(<link rel="canonical" href=")[^"]*/, `$1${canonical}`)
    .replace('<div id="root"></div>', () => `<div id="root"${markup ? ` data-prerendered="${path}"` : ''}>${markup}</div>`)
}
await Promise.all(paths.map((path) => writeFile(path === '/' ? 'dist/index.html' : `dist${path}.html`, html(path, render(path)))))
await writeFile('dist/spa.html', html('/account', ''))
await writeFile('dist/sitemap.xml', `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${paths.map((path) => `  <url><loc>${new URL(path, siteOrigin).href}</loc></url>`).join('\n')}\n</urlset>\n`)
