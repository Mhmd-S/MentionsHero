// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ignore: ['backend/**'],

  app: {
    head: {
      titleTemplate: '%s | MentionsHero Admin',
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
    '/': { redirect: '/admin' },
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
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/ui', '@nuxtjs/device'],

  runtimeConfig: {
    public: {
      supabaseUrl: process.env.SUPABASE_URL,
      supabasePublishableKey: process.env.SUPABASE_KEY,
      backendUrl: process.env.BACKEND_URL || 'http://localhost:8001',
    },
  },
})
