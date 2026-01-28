// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ui: {
    colorMode: false
  },
    css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/hints', '@nuxt/ui'],
  runtimeConfig: {
    replicateApiKey: process.env.REPLICATE_API_KEY,
    geminiApiKey: process.env.GEMINI_API_KEY,
    supabaseUrl: process.env.SUPABASE_URL,
    supabaseServiceKey: process.env.SUPABASE_SERVICE_KEY,
    public: {
      supabaseUrl: process.env.SUPABASE_URL,
      supabasePublishableKey: process.env.SUPABASE_PUBLISHABLE_KEY,
    },
  },
})