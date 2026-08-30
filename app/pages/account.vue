<script setup lang="ts">
const { session } = useAuth()
const { subscription, isSubscribed, loading, fetchSubscription, openPortal } = useSubscription()
const { publicFetch } = usePublicApi()

const firstName = ref('')
const lastName = ref('')
const phone = ref('')
const profileLoading = ref(false)
const profileSaving = ref(false)
const profileSaved = ref(false)

async function fetchProfile() {
  if (!session.value) return
  profileLoading.value = true
  try {
    const data = await publicFetch<{ first_name: string | null; last_name: string | null; phone: string | null }>('/api/profile')
    firstName.value = data.first_name || ''
    lastName.value = data.last_name || ''
    phone.value = data.phone || ''
  } catch {
    // Profile may not exist yet
  } finally {
    profileLoading.value = false
  }
}

async function saveProfile() {
  profileSaving.value = true
  profileSaved.value = false
  try {
    await publicFetch('/api/profile', {
      method: 'PUT',
      body: {
        first_name: firstName.value || null,
        last_name: lastName.value || null,
        phone: phone.value || null,
      },
    })
    profileSaved.value = true
    setTimeout(() => { profileSaved.value = false }, 3000)
  } catch {
    // handle error silently
  } finally {
    profileSaving.value = false
  }
}

onMounted(() => {
  if (session.value) {
    fetchSubscription()
    fetchProfile()
  }
})

function formatDate(dateString: string | null) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

// SEO meta tags (private page - keep out of search results)
useSeoMeta({
  title: 'Account',
  description: 'Manage your MentionsHero profile and premium subscription.',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <UPageHeader title="Account" />

    <div v-if="!session" class="text-center py-16 text-muted">
      <UIcon name="i-lucide-circle-user" class="size-12 mx-auto mb-4 opacity-40" />
      <p class="mb-4">Please sign in to view your account.</p>
      <UButton to="/login">Sign In</UButton>
    </div>

    <div v-else class="space-y-6">
      <!-- User Info -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-user" class="size-4 text-primary" />
            <h2 class="font-semibold">Profile</h2>
          </div>
        </template>

        <div v-if="profileLoading" class="flex justify-center py-4">
          <UIcon name="i-lucide-loader" class="size-5 animate-spin text-muted" />
        </div>

        <form v-else class="space-y-4" @submit.prevent="saveProfile">
          <div class="flex items-center justify-between gap-4">
            <span class="text-sm text-muted shrink-0">Email</span>
            <span class="text-sm font-medium truncate">{{ session.user.email }}</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <UFormField label="First Name">
              <UInput v-model="firstName" placeholder="First name" class="w-full" />
            </UFormField>
            <UFormField label="Last Name">
              <UInput v-model="lastName" placeholder="Last name" class="w-full" />
            </UFormField>
          </div>

          <UFormField label="Phone">
            <UInput v-model="phone" type="tel" placeholder="+1 (555) 000-0000" class="w-full" />
          </UFormField>

          <div class="flex items-center gap-3">
            <UButton type="submit" :loading="profileSaving">
              Save Profile
            </UButton>
            <span v-if="profileSaved" class="text-sm text-green-600">Saved</span>
          </div>
        </form>
      </UCard>

      <!-- Subscription -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-credit-card" class="size-4 text-primary" />
              <h2 class="font-semibold">Subscription</h2>
            </div>
            <UBadge
              :color="isSubscribed ? 'success' : 'neutral'"
              :variant="isSubscribed ? 'subtle' : 'soft'"
            >
              {{ isSubscribed ? 'Active' : subscription?.status || 'No Subscription' }}
            </UBadge>
          </div>
        </template>

        <div v-if="loading" class="flex justify-center py-4">
          <UIcon name="i-lucide-loader" class="size-5 animate-spin text-muted" />
        </div>

        <div v-else-if="isSubscribed" class="space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted">Status</span>
            <span class="text-sm font-medium capitalize">{{ subscription?.status }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted">Current Period Ends</span>
            <span class="text-sm font-medium">{{ formatDate(subscription?.current_period_end) }}</span>
          </div>
          <USeparator />
          <UButton variant="outline" block @click="openPortal">
            Manage Subscription
          </UButton>
        </div>

        <div v-else class="text-center py-4">
          <p class="text-sm text-muted mb-4">You don't have an active subscription.</p>
          <UButton to="/pricing" color="primary">View Plans</UButton>
        </div>
      </UCard>
    </div>
  </div>
</template>
