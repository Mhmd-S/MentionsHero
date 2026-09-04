<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: false })

useSeoMeta({
  title: 'Admin Sign In',
  description: 'Sign in to the MentionsHero admin.',
  robots: 'noindex, nofollow',
})

// The site has no visitor accounts — the archive is free and anonymous. This page
// exists only to unlock /admin, and accounts are created in the Supabase
// dashboard, so there is no sign-up and no password-reset flow here.
const route = useRoute()
const { login, error: authError, loading, ensureProfileLoaded, role } = useAuth()
const session = useSupabaseSession()

const externalError = ref<string | null>(
  typeof route.query.error === 'string' ? route.query.error.replace(/\+/g, ' ') : null,
)
const error = computed(() => externalError.value || authError.value)

// Presentation only: name what failed, so the alert body can carry the detail.
const errorTitle = computed(() =>
  externalError.value ? 'That link did not work' : 'We could not sign you in',
)

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type Schema = z.output<typeof schema>

const state = reactive({ email: '', password: '' })

async function onSubmit(event: FormSubmitEvent<Schema>) {
  externalError.value = null

  const success = await login(event.data.email, event.data.password)
  if (!success) return

  // Honour the page the guard bounced them from, then fall back to role routing.
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return navigateTo(redirect)
  }

  await ensureProfileLoaded()
  return navigateTo(role.value === 'admin' ? '/admin' : '/')
}

// Already signed in — no reason to show a login form.
onMounted(() => {
  if (session.value) navigateTo('/')
})
</script>

<template>
  <div class="min-h-screen bg-default">
    <!-- The night side. Says what the product does before asking for anything. -->


    <!-- The form side. -->
    <main class="flex min-h-screen flex-col justify-center px-5 py-12">
      <div class="mx-auto w-full max-w-sm">
        <NuxtLink
          to="/"
          class="mb-10 inline-flex items-center gap-2 text-highlighted lg:hidden"
        >
          <UiBrandMark :size="18" />
          <span class="text-sm font-bold tracking-[-0.02em]">MentionsHero</span>
        </NuxtLink>

        <div class="mb-8">
          <h1 class="type-title">Admin sign in</h1>
          <p class="type-meta mt-2 text-muted">
            The transcripts are free and need no account. This is the way into the
            dashboard.
          </p>
        </div>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="errorTitle"
          :description="error"
          class="mb-6"
        />

        <UForm :schema="schema" :state="state" class="space-y-5" @submit="onSubmit">
          <UFormField label="Email" name="email">
            <UInput
              v-model="state.email"
              type="email"
              size="lg"
              autocomplete="email"
              placeholder="you@example.com"
              class="w-full"
            />
          </UFormField>

          <UFormField label="Password" name="password">
            <UInput
              v-model="state.password"
              type="password"
              size="lg"
              autocomplete="current-password"
              placeholder="Your password"
              class="w-full"
            />
          </UFormField>

          <UButton type="submit" block size="lg" :loading="loading" label="Sign in" />
        </UForm>

        <USeparator class="my-8" />

        <div class="flex flex-wrap items-center justify-end gap-3">
          <ULink
            to="/"
            class="inline-flex items-center gap-1 type-meta text-muted transition-colors hover:text-default"
          >
            <UIcon name="i-lucide-chevron-left" class="size-4" aria-hidden="true" />
            Transcripts
          </ULink>
        </div>
      </div>
    </main>
  </div>
</template>
