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
        { rel: 'icon', href: '/favicon.ico' },
      ],
    },
  },

  nitro: {
    alias: {
      '~': fileURLToPath(new URL('.', import.meta.url))
    }
  },
  routeRules: {
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
  modules: ['@nuxt/eslint', '@nuxt/hints', '@nuxt/ui', '@nuxtjs/seo'],

  sitemap: {
    exclude: ['/admin/**', '/login', '/signup', '/account'],
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