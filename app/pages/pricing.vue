<script setup lang="ts">
const { session } = useAuth()
const { isSubscribed, startCheckout, loading } = useSubscription()

useSeoMeta({
  title: 'Pricing',
  description: 'Get unlimited access to all premium press briefing transcripts. Free and premium plans available.',
  ogTitle: 'Pricing | MentionsHero',
  ogDescription: 'Get unlimited access to all premium press briefing transcripts.',
  twitterCard: 'summary',
})

useSchemaOrg([
  defineBreadcrumb({
    itemListElement: [
      { name: 'Home', item: '/' },
      { name: 'Pricing' },
    ],
  }),
  {
    '@type': 'FAQPage',
    'mainEntity': [
      {
        '@type': 'Question',
        'name': 'What do I get with a premium subscription?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'Premium subscribers get unlimited access to all press briefing transcripts, full search and analysis tools, and speaker frequency breakdowns.',
        },
      },
      {
        '@type': 'Question',
        'name': 'How much does MentionsHero cost?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'MentionsHero offers a free plan with access to free transcripts, and a premium plan at $20/month for full access to all transcripts and analysis features.',
        },
      },
      {
        '@type': 'Question',
        'name': 'Can I cancel my subscription anytime?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'Yes, you can cancel your subscription at any time from your account page. You will retain access until the end of your current billing period.',
        },
      },
      {
        '@type': 'Question',
        'name': 'What transcripts are available for free?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'Free users can browse all transcripts, view non-premium transcripts, and search within available transcripts. Premium transcripts require a subscription.',
        },
      },
    ],
  },
])
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
            Browse all transcripts
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

    <div class="mt-16 max-w-2xl mx-auto">
      <h2 class="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
      <div class="space-y-4">
        <UCard>
          <template #header>
            <p class="font-semibold text-sm">What do I get with a premium subscription?</p>
          </template>
          <p class="text-sm text-muted">Premium subscribers get unlimited access to all press briefing transcripts, full search and analysis tools, and speaker frequency breakdowns.</p>
        </UCard>
        <UCard>
          <template #header>
            <p class="font-semibold text-sm">How much does MentionsHero cost?</p>
          </template>
          <p class="text-sm text-muted">MentionsHero offers a free plan with access to free transcripts, and a premium plan at $20/month for full access to all transcripts and analysis features.</p>
        </UCard>
        <UCard>
          <template #header>
            <p class="font-semibold text-sm">Can I cancel my subscription anytime?</p>
          </template>
          <p class="text-sm text-muted">Yes, you can cancel your subscription at any time from your account page. You will retain access until the end of your current billing period.</p>
        </UCard>
        <UCard>
          <template #header>
            <p class="font-semibold text-sm">What transcripts are available for free?</p>
          </template>
          <p class="text-sm text-muted">Free users can browse all transcripts, view non-premium transcripts, and search within available transcripts. Premium transcripts require a subscription.</p>
        </UCard>
      </div>
    </div>
  </div>
</template>
