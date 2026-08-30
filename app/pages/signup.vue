<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: false })

useSeoMeta({
  title: 'Sign Up',
  description: 'Create a free MentionsHero account to access press briefing transcripts and mentions analysis.',
  robots: 'noindex, nofollow',
})

const { signup, error, loading, resendConfirmation } = useAuth()
const session = useSupabaseSession()

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(8, 'Use at least 8 characters'),
})

type Schema = z.output<typeof schema>

const state = reactive({ email: '', password: '' })

const emailSent = ref(false)
const resending = ref(false)
const resent = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  const result = await signup(event.data.email, event.data.password)
  if (!result.ok) return

  if (result.needsConfirmation) {
    emailSent.value = true
    return
  }

  // Email confirmation is off on this project — straight in.
  return navigateTo('/')
}

async function onResend() {
  resending.value = true
  resent.value = false
  try {
    resent.value = await resendConfirmation(state.email)
  } finally {
    resending.value = false
  }
}

onMounted(() => {
  if (session.value) navigateTo('/')
})
</script>

<template>
  <div class="min-h-screen bg-default lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
    <!-- The night side. Same panel as sign-in: one identity across the flow. -->
    <aside class="hidden flex-col justify-between bg-ink-950 px-12 py-12 lg:flex lg:border-r lg:border-ink-800">
      <NuxtLink
        to="/"
        class="inline-flex w-fit items-center gap-2 text-paper-50 transition-opacity hover:opacity-80"
      >
        <UiBrandMark :size="20" />
        <span class="text-base font-bold tracking-[-0.02em]">MentionsHero</span>
      </NuxtLink>

      <div class="max-w-md">
        <p class="type-display text-paper-50">
          We count what they <mark>say</mark>.
        </p>
        <p class="mt-5 text-base text-ink-200">
          Every briefing transcribed, every tracked word marked, and the market
          price for that word sitting right next to the count.
        </p>

        <ul class="mt-9 space-y-4 border-t border-ink-800 pt-7">
          <li class="flex items-start gap-3 text-sm text-ink-200">
            <UIcon name="i-lucide-file-text" class="mt-0.5 size-4 shrink-0 text-mark-500" aria-hidden="true" />
            <span>Full transcripts of press briefings, with speakers separated.</span>
          </li>
          <li class="flex items-start gap-3 text-sm text-ink-200">
            <UIcon name="i-lucide-hash" class="mt-0.5 size-4 shrink-0 text-mark-500" aria-hidden="true" />
            <span>Mention counts for any term, across a speaker's whole archive.</span>
          </li>
          <li class="flex items-start gap-3 text-sm text-ink-200">
            <UIcon name="i-lucide-chart-bar" class="mt-0.5 size-4 shrink-0 text-mark-500" aria-hidden="true" />
            <span>The Kalshi and Polymarket price for the word, beside the count.</span>
          </li>
        </ul>
      </div>

      <p class="type-label text-ink-300">
        Market data — Kalshi &amp; Polymarket
      </p>
    </aside>

    <main class="flex min-h-screen flex-col justify-center px-5 py-12 sm:px-10">
      <div class="mx-auto w-full max-w-sm">
        <NuxtLink
          to="/"
          class="mb-10 inline-flex items-center gap-2 text-highlighted lg:hidden"
        >
          <UiBrandMark :size="18" />
          <span class="text-sm font-bold tracking-[-0.02em]">MentionsHero</span>
        </NuxtLink>

        <!-- The account exists; the link is in flight. This is a real step in
             the flow, so it gets the whole column, not a squeezed panel. -->
        <div v-if="emailSent">
          <div class="flex size-12 items-center justify-center rounded-sm border border-default bg-elevated">
            <UIcon name="i-lucide-mail-open" class="size-6 text-highlighted" aria-hidden="true" />
          </div>

          <h1 class="type-title mt-6">Check your email</h1>
          <p class="mt-3 text-base text-muted">We sent a confirmation link to</p>
          <p class="type-figure mt-1 break-all text-base text-highlighted">{{ state.email }}</p>

          <ol class="mt-8 border-t border-default">
            <li class="flex items-baseline gap-3 rule-dotted py-3">
              <span class="type-figure text-sm text-dimmed">1</span>
              <span class="type-meta text-toned">Open the message from MentionsHero.</span>
            </li>
            <li class="flex items-baseline gap-3 rule-dotted py-3">
              <span class="type-figure text-sm text-dimmed">2</span>
              <span class="type-meta text-toned">Follow the confirmation link.</span>
            </li>
            <li class="flex items-baseline gap-3 py-3">
              <span class="type-figure text-sm text-dimmed">3</span>
              <span class="type-meta text-toned">You land back here signed in. Nothing else to fill in.</span>
            </li>
          </ol>

          <UAlert
            v-if="resent"
            color="primary"
            variant="subtle"
            icon="i-lucide-mail-check"
            title="Sent again"
            :description="`A fresh confirmation link is on its way to ${state.email}.`"
            class="mt-6"
          />
          <UAlert
            v-else-if="error"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            title="We could not resend that email"
            :description="error"
            class="mt-6"
          />

          <div class="mt-8 flex flex-col gap-2">
            <UButton
              variant="subtle"
              color="neutral"
              block
              size="lg"
              :loading="resending"
              icon="i-lucide-rotate-cw"
              label="Resend the email"
              @click="onResend"
            />
            <UButton to="/login" variant="ghost" color="neutral" block size="lg" label="Back to sign in" />
          </div>

          <p class="type-caption mt-6 text-dimmed">
            Nothing after a couple of minutes? Look in your spam folder, then resend.
          </p>
        </div>

        <!-- Signup form -->
        <template v-else>
          <div class="mb-8">
            <p class="type-label text-dimmed">Create account</p>
            <h1 class="type-title mt-2">Start tracking mentions</h1>
            <p class="type-meta mt-2 text-muted">
              An email and a password. That is the whole form — free, no card.
            </p>
          </div>

          <UAlert
            v-if="error"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            title="We could not create your account"
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

            <UFormField label="Password" name="password" hint="At least 8 characters">
              <UInput
                v-model="state.password"
                type="password"
                size="lg"
                autocomplete="new-password"
                placeholder="Create a password"
                class="w-full"
              />
            </UFormField>

            <UButton type="submit" block size="lg" :loading="loading" label="Create account" />
          </UForm>

          <p class="type-caption mt-4 text-dimmed">
            Add your name and phone later on your account page, if you want to.
          </p>

          <USeparator class="my-8" />

          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="type-meta text-muted">
              Already have an account?
              <ULink to="/login" class="font-medium text-default underline underline-offset-4">
                Sign in
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
        </template>
      </div>
    </main>
  </div>
</template>
