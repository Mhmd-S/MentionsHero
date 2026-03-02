<script setup lang="ts">
const { session } = useAuth()
const { isSubscribed, startCheckout, loading } = useSubscription()
</script>

<template>
  <div class="max-w-4xl pt-8 mx-auto">
    <div class="text-center mb-12">
      <h1 class="text-3xl font-bold mb-3">Pricing</h1>
      <p class="text-gray-600 dark:text-gray-400 text-lg">
        Access all transcripts with a premium subscription
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
      <!-- Free Tier -->
      <UCard>
        <template #header>
          <div>
            <h2 class="text-xl font-bold">Free</h2>
            <div class="text-3xl font-bold mt-2">$0<span class="text-sm font-normal text-gray-500">/month</span></div>
          </div>
        </template>

        <ul class="space-y-3">
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            Browse all personas
          </li>
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            View free transcripts
          </li>
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            Search within transcripts
          </li>
          <li class="flex items-center gap-2 text-sm text-gray-400">
            <UIcon name="i-lucide-x" class="size-5" />
            Premium transcripts
          </li>
        </ul>

        <template #footer>
          <NuxtLink v-if="!session" to="/signup">
            <UButton variant="outline" block>Get Started</UButton>
          </NuxtLink>
          <UButton v-else variant="outline" block disabled>Current Plan</UButton>
        </template>
      </UCard>

      <!-- Premium Tier -->
      <UCard class="ring-2 ring-primary">
        <template #header>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-xl font-bold">Premium</h2>
              <UBadge color="primary" variant="subtle" size="xs">Recommended</UBadge>
            </div>
            <div class="text-3xl font-bold mt-2">$20<span class="text-sm font-normal text-gray-500">/month</span></div>
          </div>
        </template>

        <ul class="space-y-3">
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            Everything in Free
          </li>
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            All premium transcripts
          </li>
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            Full search & analysis
          </li>
          <li class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-check" class="size-5 text-green-500" />
            Speaker frequency breakdown
          </li>
        </ul>

        <template #footer>
          <template v-if="isSubscribed">
            <UButton color="primary" block disabled>Subscribed</UButton>
          </template>
          <template v-else-if="session">
            <UButton color="primary" block :loading="loading" @click="startCheckout">
              Subscribe
            </UButton>
          </template>
          <template v-else>
            <NuxtLink to="/signup">
              <UButton color="primary" block>Sign Up & Subscribe</UButton>
            </NuxtLink>
          </template>
        </template>
      </UCard>
    </div>
  </div>
</template>
