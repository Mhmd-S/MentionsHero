// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ignore: ['backend/**'],
  nitro: {
    alias: {
      '~': fileURLToPath(new URL('.', import.meta.url))
    }
  },
  routeRules: {
    '/api/**': {
      proxy: 'http://localhost:8001/api/**'
    },
    '/view/**': { robots: false },
    '/login': { robots: false },
    '/signup': { robots: false },
    '/admin/**': { robots: false },
  },
  icon: {
    clientBundle: {
      scan: true,
    },
    serverBundle: false,
  },
  ui: {
    colorMode: false
  },
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/hints', '@nuxt/ui', '@nuxtjs/seo'],
  runtimeConfig: {
    public: {
      supabaseUrl: process.env.SUPABASE_URL,
      supabasePublishableKey: process.env.SUPABASE_KEY,
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || 'https://chanis.app',
    },
  },
  site: {
    url: process.env.NUXT_PUBLIC_SITE_URL || 'https://chanis.app',
    name: 'Chanis',
    description: 'Press briefing transcripts for Kalshi and Polymarket mentions market traders.',
    defaultLocale: 'en',
  },
  robots: {
    disallow: ['/admin/', '/login', '/signup', '/view/'],
  },
  sitemap: {
    sources: ['/api/__sitemap__/urls'],
  },
  schemaOrg: {
    identity: { type: 'WebSite', name: 'Chanis' },
  },
  ogImage: {
    enabled: false,
  },
})