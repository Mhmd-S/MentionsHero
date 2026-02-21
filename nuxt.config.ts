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
    }
  },
  icon: {
    clientBundle: {
      scan: true,
    },
    serverBundle: false,
  },
  ui: {
    colorMode: true
  },
    css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/hints', '@nuxt/ui'],
  runtimeConfig: {
    public: {
      supabaseUrl: process.env.SUPABASE_URL,
      supabasePublishableKey: process.env.SUPABASE_KEY,
    },
  },
})