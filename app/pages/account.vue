<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const route = useRoute()
const user = useSupabaseUser()
const { profile, loading: profileLoading, saveProfile } = useProfile()
const {
  subscription,
  isSubscribed,
  loading: subscriptionLoading,
  checkoutPending,
  error: subscriptionError,
  fetchSubscription,
  openPortal,
} = useSubscription()

useSeoMeta({
  title: 'Account',
  description: 'Manage your MentionsHero profile and premium subscription.',
  robots: 'noindex, nofollow',
})

// Set by /auth/confirm after a successful email confirmation.
const justConfirmed = computed(() => route.query.welcome === '1')

// The route is guarded, so `user` is present — but the JWT claims carry the email,
// which is why nothing here has to ask for it.
const email = computed(() => (user.value?.email as string | undefined) ?? '')

const schema = z.object({
  first_name: z.string().max(100).optional(),
  last_name: z.string().max(100).optional(),
  phone: z.string().max(40).optional(),
})

type Schema = z.output<typeof schema>

const state = reactive({ first_name: '', last_name: '', phone: '' })

// Seed the form from the profile as soon as it lands, and keep it in sync if the
// profile is reloaded (e.g. after returning from Stripe).
watchEffect(() => {
  if (!profile.value) return
  state.first_name = profile.value.first_name ?? ''
  state.last_name = profile.value.last_name ?? ''
  state.phone = profile.value.phone ?? ''
})

const saving = ref(false)
const saved = ref(false)
const saveError = ref<string | null>(null)

// --- Password -------------------------------------------------------------
// Arriving from a reset link (/auth/confirm?type=recovery) signs the user in but
// gives them nowhere to choose a new password. This is that place, and ?recovery=1
// opens it focused so the link lands on something actionable.
const { updatePassword, error: authError } = useAuth()

const passwordSchema = z
  .object({
    password: z.string().min(8, 'Use at least 8 characters'),
    confirm: z.string(),
  })
  .refine(data => data.password === data.confirm, {
    message: 'Both passwords must match',
    path: ['confirm'],
  })

type PasswordSchema = z.output<typeof passwordSchema>

const passwordState = reactive({ password: '', confirm: '' })
const passwordOpen = ref(route.query.recovery === '1')
const passwordSaving = ref(false)
const passwordSaved = ref(false)

async function onChangePassword(event: FormSubmitEvent<PasswordSchema>) {
  passwordSaving.value = true
  passwordSaved.value = false
  try {
    if (await updatePassword(event.data.password)) {
      passwordSaved.value = true
      passwordState.password = ''
      passwordState.confirm = ''
      passwordOpen.value = false
    }
  } finally {
    passwordSaving.value = false
  }
}

async function onSave(event: FormSubmitEvent<Schema>) {
  saving.value = true
  saved.value = false
  saveError.value = null
  try {
    await saveProfile({
      first_name: event.data.first_name?.trim() || null,
      last_name: event.data.last_name?.trim() || null,
      phone: event.data.phone?.trim() || null,
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    // Previously an empty catch: a failed save looked exactly like a slow one.
    saveError.value = e instanceof Error ? e.message : 'Could not save your details'
  } finally {
    saving.value = false
  }
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

// Presentation only. Green and red are reserved for market outcome and trend,
// so a healthy subscription reads as ink (the premium voice) and only a billing
// problem — something the user must act on — is allowed to shout.
const statusColor = computed(() => {
  const status = subscription.value?.status
  if (status === 'active' || status === 'trialing') return 'primary'
  if (status === 'past_due' || status === 'unpaid') return 'error'
  return 'neutral'
})
const statusLabel = computed(() => (subscription.value?.status ?? '').replace(/_/g, ' '))

onMounted(() => {
  // Returning from Stripe Checkout: the webhook may still be in flight, so re-read.
  if (route.query.session_id) fetchSubscription()
})
</script>

<template>
  <div class="mx-auto w-full max-w-4xl pb-20">
    <UPageHeader
      title="Account"
      description="Your details, your subscription, and what it covers."
      :ui="{
        title: 'text-2xl sm:text-2xl text-highlighted',
        description: 'mt-4 measure text-base text-muted',
        headline: 'mb-3 type-label text-xs font-medium text-dimmed flex items-center gap-2',
      }"
    />

    <UAlert
      v-if="justConfirmed"
      color="primary"
      variant="subtle"
      icon="i-lucide-party-popper"
      title="Your email is confirmed"
      description="You are signed in and ready to read. Adding your name below is optional."
      class="mt-6"
      :actions="[{ label: 'Go to transcripts', to: '/', color: 'neutral', variant: 'outline', trailingIcon: 'i-lucide-arrow-right' }]"
    />

    <div class="mt-10 space-y-12">
      <!-- Profile. Section label hangs in the margin on wide screens. -->
      <section class="lg:grid lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-10">
        <div class="mb-4 lg:mb-0">
          <h2 class="type-label text-dimmed">Profile</h2>
          <p class="type-meta mt-2 hidden text-muted lg:block">
            How we address you, and how we reach you about the account.
          </p>
        </div>

        <UCard>
          <UiLoadingBlock
            v-if="profileLoading && !profile"
            variant="rows"
            :count="3"
            label="Loading your profile"
          />

          <UForm v-else :schema="schema" :state="state" class="space-y-6" @submit="onSave">
            <UiStatRow label="Email" divided>
              <span class="break-all">{{ email }}</span>
            </UiStatRow>

            <p class="type-meta text-muted">
              The rest is optional. We only use it if we have to contact you about your account.
            </p>

            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <UFormField label="First name" name="first_name">
                <UInput
                  v-model="state.first_name"
                  autocomplete="given-name"
                  placeholder="First name"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Last name" name="last_name">
                <UInput
                  v-model="state.last_name"
                  autocomplete="family-name"
                  placeholder="Last name"
                  class="w-full"
                />
              </UFormField>
            </div>

            <UFormField label="Phone" name="phone">
              <UInput
                v-model="state.phone"
                type="tel"
                autocomplete="tel"
                placeholder="+1 (555) 000-0000"
                class="w-full"
              />
            </UFormField>

            <UAlert
              v-if="saveError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              title="We could not save your details"
              :description="saveError"
            />

            <div class="flex items-center gap-4">
              <UButton type="submit" :loading="saving" label="Save changes" />
              <span class="type-label flex items-center gap-1.5 text-muted" aria-live="polite">
                <template v-if="saved">
                  <UIcon name="i-lucide-check" class="size-3.5" aria-hidden="true" />
                  Saved
                </template>
              </span>
            </div>
          </UForm>
        </UCard>
      </section>

      <!-- Password -->
      <section class="lg:grid lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-10">
        <div class="mb-4 lg:mb-0">
          <h2 class="type-label text-dimmed">Password</h2>
          <p class="type-meta mt-2 hidden text-muted lg:block">
            Used with your email to sign in.
          </p>
        </div>

        <UCard>
          <UAlert
            v-if="passwordSaved"
            color="primary"
            variant="subtle"
            icon="i-lucide-check"
            title="Password updated"
            description="Use your new password the next time you sign in."
            class="mb-6"
          />

          <div v-if="!passwordOpen" class="flex flex-wrap items-center justify-between gap-4">
            <p class="type-meta text-muted">Choose a new password for this account.</p>
            <UButton
              variant="subtle"
              color="neutral"
              icon="i-lucide-key-round"
              label="Change password"
              @click="passwordOpen = true"
            />
          </div>

          <UForm
            v-else
            :schema="passwordSchema"
            :state="passwordState"
            class="space-y-5"
            @submit="onChangePassword"
          >
            <UFormField label="New password" name="password" hint="At least 8 characters">
              <UInput
                v-model="passwordState.password"
                type="password"
                autocomplete="new-password"
                placeholder="New password"
                class="w-full"
              />
            </UFormField>

            <UFormField label="Confirm new password" name="confirm">
              <UInput
                v-model="passwordState.confirm"
                type="password"
                autocomplete="new-password"
                placeholder="Repeat the new password"
                class="w-full"
              />
            </UFormField>

            <UAlert
              v-if="authError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              title="We could not update your password"
              :description="authError"
            />

            <div class="flex items-center gap-3">
              <UButton type="submit" :loading="passwordSaving" label="Update password" />
              <UButton
                variant="ghost"
                color="neutral"
                label="Cancel"
                @click="passwordOpen = false"
              />
            </div>
          </UForm>
        </UCard>
      </section>

      <!-- Subscription -->
      <section class="lg:grid lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-10">
        <div class="mb-4 lg:mb-0">
          <h2 class="type-label text-dimmed">Subscription</h2>
          <p class="type-meta mt-2 hidden text-muted lg:block">
            Billing runs through Stripe. Cancel or change your card there at any time.
          </p>
        </div>

        <UCard>
          <UiLoadingBlock
            v-if="subscriptionLoading && !subscription"
            variant="rows"
            :count="2"
            label="Loading your subscription"
          />

          <div v-else class="space-y-6">
            <UAlert
              v-if="subscriptionError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              title="We could not load your subscription"
              :description="subscriptionError"
              :actions="[{ label: 'Try again', color: 'neutral', variant: 'outline', onClick: () => fetchSubscription() }]"
            />

            <template v-if="isSubscribed">
              <div class="space-y-3">
                <UiStatRow v-if="subscription?.status" label="Status" divided>
                  <UBadge :color="statusColor" variant="subtle" class="capitalize">
                    {{ statusLabel }}
                  </UBadge>
                </UiStatRow>
                <UiStatRow label="Renews" :value="formatDate(subscription?.current_period_end ?? null)" />
              </div>

              <p class="type-meta text-muted">
                Premium is on: every transcript, term search across a speaker's archive,
                and the full mentions analysis on every market.
              </p>

              <UButton
                variant="subtle"
                color="neutral"
                icon="i-lucide-external-link"
                :loading="checkoutPending"
                label="Manage subscription"
                @click="openPortal"
              />
            </template>

            <template v-else>
              <UiStatRow v-if="subscription?.status" label="Status" divided>
                <UBadge :color="statusColor" variant="subtle" class="capitalize">
                  {{ statusLabel }}
                </UBadge>
              </UiStatRow>

              <UiUpsellBanner
                variant="panel"
                title="You are on the free plan"
                description="Premium unlocks every transcript, term search across a speaker's whole archive, and the full mentions analysis on every market."
                cta-label="See pricing"
                cta-to="/pricing"
              />
            </template>
          </div>
        </UCard>
      </section>
    </div>
  </div>
</template>
