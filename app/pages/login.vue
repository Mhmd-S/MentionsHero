<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: false })

useSeoMeta({
  title: 'Sign In',
  description: 'Sign in to your MentionsHero account.',
  robots: 'noindex, nofollow',
})

const route = useRoute()
const { login, error: authError, loading, sendPasswordReset, ensureProfileLoaded, role } = useAuth()
const session = useSupabaseSession()

// A failed email link redirects here with ?error=
const externalError = ref<string | null>(
  typeof route.query.error === 'string' ? route.query.error.replace(/\+/g, ' ') : null,
)
const error = computed(() => externalError.value || authError.value)
const notice = ref<string | null>(null)
const resetting = ref(false)

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
  notice.value = null

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

async function onForgotPassword() {
  externalError.value = null
  notice.value = null

  if (!state.email.trim()) {
    externalError.value = 'Type your email address in the field above, then choose Forgot password.'
    return
  }

  resetting.value = true
  try {
    if (await sendPasswordReset(state.email.trim())) {
      notice.value = `We sent a reset link to ${state.email.trim()}. Open it to choose a new password.`
    }
  } finally {
    resetting.value = false
  }
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
          <h1 class="type-title">Welcome back</h1>
          <p class="type-meta mt-2 text-muted">
            Sign in to read the transcripts and see the counts behind every market.
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
        <UAlert
          v-else-if="notice"
          color="primary"
          variant="subtle"
          icon="i-lucide-mail-check"
          title="Check your inbox"
          :description="notice"
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
            <template #hint>
              <UButton
                variant="link"
                color="neutral"
                size="xs"
                class="p-0"
                :loading="resetting"
                @click="onForgotPassword"
              >
                Forgot password?
              </UButton>
            </template>
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

        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="type-meta text-muted">
            No account yet?
            <ULink to="/signup" class="font-medium text-default underline underline-offset-4">
              Create one
            </ULink>
          </p>
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
