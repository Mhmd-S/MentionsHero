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
      ],
    },
  },

  nitro: {
    alias: {
      '~': fileURLToPath(new URL('.', import.meta.url))
    }
  },
  routeRules: {
    '/api/_nuxt_icon/**': {},
    '/api/**': {
      proxy: 'http://localhost:8001/api/**'
    }
  },
  icon: {
    clientBundle: {
      scan: true,
    },
    serverBundle: false,
  },
  ui: {},
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/hints', '@nuxt/ui', '@nuxtjs/seo', '@nuxtjs/device', '@nuxt/image', '@nuxt/content'],

  image: {
    quality: 80,
    formats: ['webp'],
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
    ],
  },

  robots: {
    disallow: ['/admin/', '/account'],
  },

  runtimeConfig: {
    public: {
      supabaseUrl: process.env.SUPABASE_URL,
      supabasePublishableKey: process.env.SUPABASE_KEY,
    },
  },
})