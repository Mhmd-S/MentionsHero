<script setup lang="ts">
const { session } = useAuth()
const { subscription, isSubscribed, loading, fetchSubscription, openPortal } = useSubscription()

onMounted(() => {
  if (session.value) {
    fetchSubscription()
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
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-3xl font-bold mb-8">Account</h1>

    <div v-if="!session" class="text-center py-12 text-gray-500">
      <p>Please sign in to view your account.</p>
      <NuxtLink to="/login">
        <UButton class="mt-4">Sign In</UButton>
      </NuxtLink>
    </div>

    <div v-else class="space-y-6">
      <!-- User Info -->
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">Profile</h2>
        </template>
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500">Email</span>
            <span class="text-sm font-medium">{{ session.user.email }}</span>
          </div>
        </div>
      </UCard>

      <!-- Subscription -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Subscription</h2>
            <UBadge
              :color="isSubscribed ? 'success' : 'neutral'"
              :variant="isSubscribed ? 'subtle' : 'soft'"
            >
              {{ isSubscribed ? 'Active' : subscription?.status || 'No Subscription' }}
            </UBadge>
          </div>
        </template>

        <div v-if="loading" class="flex justify-center py-4">
          <UIcon name="i-heroicons-arrow-path" class="size-5 animate-spin" />
        </div>

        <div v-else-if="isSubscribed" class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500">Status</span>
            <span class="text-sm font-medium capitalize">{{ subscription?.status }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500">Current Period Ends</span>
            <span class="text-sm font-medium">{{ formatDate(subscription?.current_period_end) }}</span>
          </div>

          <UButton variant="outline" block @click="openPortal">
            Manage Subscription
          </UButton>
        </div>

        <div v-else class="text-center py-4">
          <p class="text-sm text-gray-500 mb-4">You don't have an active subscription.</p>
          <NuxtLink to="/pricing">
            <UButton color="primary">View Plans</UButton>
          </NuxtLink>
        </div>
      </UCard>
    </div>
  </div>
</template>
