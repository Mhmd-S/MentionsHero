// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ignore: ['backend/**'],

  site: {
    url: 'https://mentionshero.com',
    name: 'MentionsHero',
    description: 'Search and analyze press briefing transcripts. Track what public figures say, linked to Kalshi mentions prediction markets.',
    defaultLocale: 'en',
  },

  app: {
    head: {
      titleTemplate: '%s | MentionsHero',
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'alternate', type: 'application/rss+xml', title: 'MentionsHero Blog', href: '/rss.xml' },
      ],
    },
  },

  nitro: {
    alias: {
      '~': fileURLToPath(new URL('.', import.meta.url))
    }
  },
  routeRules: {
    // Everything under /api belongs to FastAPI. Nitro MERGES route rules rather than
    // letting a more specific key opt out, so the old `'/api/_nuxt_icon/**': {}` did
    // not exclude the icon endpoint from this proxy — icon requests were forwarded to
    // the backend, which 404s them. That is what produced
    // `[Icon] failed to load icon lucide:sun|menu|hash`. The icon API is moved off
    // the /api namespace entirely below.
    '/api/**': {
      proxy: 'http://localhost:8001/api/**'
    }
  },
  icon: {
    // Default is /api/_nuxt_icon, which collides with the FastAPI proxy above.
    localApiEndpoint: '/_nuxt_icon',
    clientBundle: {
      scan: true,
    },
    // Bundle the icons the server renders too. With serverBundle disabled, SSR
    // resolved every icon over the network against the Iconify API — which is what
    // produced `[Icon] failed to load icon` for sun/menu/hash. Every icon in the app
    // is lucide and @iconify-json/lucide is installed, so this resolves locally.
    serverBundle: 'local',
  },
  // Reads SUPABASE_URL / SUPABASE_KEY from .env via the module's own fallback chain.
  supabase: {
    // No generated Database types in this project; skips a build-time warning.
    types: false,
    // The module ships a `global-auth` middleware that redirects every route not
    // listed in `redirectOptions.exclude` to /login. This site is public by
    // default, so an allow-list is the wrong shape: one forgotten route silently
    // forces a login wall. app/middleware/auth.global.ts owns the guard instead.
    redirect: false,
    cookieOptions: {
      // The module default is 8 hours, which signed people out mid-session.
      maxAge: 60 * 60 * 24 * 30,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
    },
  },

  css: ['~/assets/css/main.css'],
  // @nuxtjs/supabase first: it registers `enforce: 'pre'` plugins that must run
  // before anything reads the session.
  modules: ['@nuxtjs/supabase', '@nuxt/eslint', '@nuxt/hints', '@nuxt/ui', '@nuxtjs/seo', '@nuxtjs/device', '@nuxt/image', '@nuxt/content'],
  
  image: {
    quality: 80,
  },

  sitemap: {
    exclude: ['/admin/**', '/login', '/signup', '/account'],
    sources: [
      `${process.env.BACKEND_URL || 'http://localhost:8001'}/api/public/sitemap-urls`,
    ],
    urls: [
      { loc: '/', changefreq: 'daily', priority: 1.0 },
      { loc: '/pricing', changefreq: 'monthly', priority: 0.6 },
      { loc: '/blog', changefreq: 'weekly', priority: 0.7 },
      { loc: '/markets', changefreq: 'daily', priority: 0.9 },
    ],
  },

  robots: {
    disallow: ['/admin/', '/account'],
  },

  runtimeConfig: {
    public: {
      // Supabase url/key now live under `public.supabase.*`, provided by @nuxtjs/supabase.
      backendUrl: process.env.BACKEND_URL || 'http://localhost:8001',
    },
  },
})