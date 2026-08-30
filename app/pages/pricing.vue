<script setup lang="ts">
const session = useSupabaseSession()
const { isSubscribed, checkoutPending, error, startCheckout } = useSubscription()

// One source of truth for the FAQ: the DOM accordion and the FAQPage schema
// below are both driven from this array, so the two can never drift apart.
const faqs = [
  {
    q: 'What do I get with a premium subscription?',
    a: 'Every transcript opens in full, keyword search runs across a speaker’s whole archive, and every tracked market term shows its mention count, its trend across briefings and the quoted context around each mention.',
  },
  {
    q: 'How much does MentionsHero cost?',
    a: 'Browsing is free. Premium costs $20 per month and unlocks every transcript plus the full mentions analysis on every market.',
  },
  {
    q: 'Can I cancel my subscription anytime?',
    a: 'Yes. Cancel from your account page at any time. You keep access until the end of the billing period you have already paid for.',
  },
  {
    q: 'What can I read for free?',
    a: 'You can browse every persona, every market and every briefing, read any transcript that is not marked premium, and search inside the transcripts you can already read.',
  },
]

const faqItems = computed(() => faqs.map(f => ({ label: f.q, content: f.a })))

// The comparison is the argument for the price, so it names real product
// surfaces rather than adjectives.
const capabilities = [
  { label: 'Browse every persona, briefing and market', free: true },
  { label: 'Read any transcript that is not premium', free: true },
  { label: 'Search inside a transcript you can read', free: true },
  { label: 'Read every premium transcript in full', free: false },
  { label: 'Search a keyword across a speaker’s whole archive', free: false },
  { label: 'Mention counts on every tracked market term', free: false },
  { label: 'Trend across briefings, and the quoted context', free: false },
]

const premiumOnly = capabilities.filter(c => !c.free)

useSeoMeta({
  title: 'Pricing',
  description: 'Browsing is free. $20 a month unlocks every transcript, archive-wide keyword search, and the mention counts behind every market.',
  ogTitle: 'Pricing | MentionsHero',
  ogDescription: 'Browsing is free. $20 a month unlocks every transcript and the mention counts behind every market.',
  twitterTitle: 'Pricing | MentionsHero',
  twitterDescription: 'Browsing is free. $20 a month unlocks every transcript and the mention counts behind every market.',
})

defineOgImage({ component: 'OgImageDefault', alt: 'Pricing | MentionsHero' })

useSchemaOrg([
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: 'Pricing' },
    ],
  }),
  {
    '@type': 'FAQPage',
    'mainEntity': faqs.map(f => ({
      '@type': 'Question',
      'name': f.q,
      'acceptedAnswer': { '@type': 'Answer', 'text': f.a },
    })),
  },
])
</script>

<template>
  <div class="py-10 sm:py-14">
    <!-- Header -->
    <header class="measure-wide">
      <p class="type-label text-dimmed">Pricing</p>
      <h1 class="type-title mt-2 text-highlighted">
        The transcript is free. The count is not.
      </h1>
      <p class="type-body mt-4 text-muted">
        Anyone can read what was said. A subscription tells you how many times a word was said,
        whether it is being said more or less, and what the market is charging for it.
        <span class="type-figure text-highlighted">$20</span> a month, cancel whenever.
      </p>
    </header>

    <div class="mt-10 grid gap-10 lg:mt-14 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:gap-14">
      <!-- Plans rail -->
      <div class="lg:sticky lg:top-24 lg:self-start">
        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="error"
          description="Nothing has been charged. Try again, or check your account page if you think you already subscribed."
          class="mb-4"
        />

        <UCard :ui="{ header: 'pb-4', footer: 'pt-4' }">
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <h2 class="type-subhead text-highlighted">Premium</h2>
              <UBadge color="secondary" variant="subtle" size="sm" label="Full access" />
            </div>
            <p class="mt-3 flex items-baseline gap-1.5">
              <span class="type-figure text-4xl font-bold text-highlighted">$20</span>
              <span class="type-label text-dimmed">/ month</span>
            </p>
          </template>

          <ul class="space-y-2.5">
            <li v-for="cap in premiumOnly" :key="cap.label" class="flex gap-2.5 text-sm">
              <UIcon name="i-lucide-check" class="mt-0.5 size-4 shrink-0 text-highlighted" aria-hidden="true" />
              <span class="text-default">{{ cap.label }}</span>
            </li>
            <li class="flex gap-2.5 text-sm">
              <UIcon name="i-lucide-check" class="mt-0.5 size-4 shrink-0 text-highlighted" aria-hidden="true" />
              <span class="text-default">Everything on the free plan</span>
            </li>
          </ul>

          <template #footer>
            <ClientOnly>
              <!-- Pre-hydration the subscription state is unknown, so the fallback is
                   the action that is correct for a signed-out visitor and for no-JS. -->
              <template #fallback>
                <UButton
                  to="/signup"
                  color="primary"
                  block
                  trailing-icon="i-lucide-arrow-right"
                  label="Start tracking"
                />
              </template>

              <UButton
                v-if="isSubscribed"
                to="/account"
                color="primary"
                variant="outline"
                block
                icon="i-lucide-circle-check"
                label="You are subscribed — manage billing"
              />
              <UButton
                v-else-if="session"
                color="primary"
                block
                :loading="checkoutPending"
                label="Subscribe for $20 a month"
                @click="startCheckout"
              />
              <UButton
                v-else
                to="/signup"
                color="primary"
                block
                trailing-icon="i-lucide-arrow-right"
                label="Start tracking"
              />
            </ClientOnly>

            <p class="type-caption mt-3 text-dimmed">
              Billed monthly through Stripe. Cancel from your account page at any time.
            </p>
          </template>
        </UCard>

        <div class="mt-4 rounded-sm border border-default p-4">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold text-highlighted">Free</h2>
            <span class="type-figure text-sm text-dimmed">$0</span>
          </div>
          <p class="mt-1 text-sm text-muted">
            Browse the archive, read every non-premium transcript, and search inside it.
          </p>
          <ClientOnly>
            <template #fallback>
              <UButton
                to="/signup"
                variant="outline"
                color="neutral"
                block
                class="mt-3"
                label="Create a free account"
              />
            </template>
            <UButton
              v-if="!session"
              to="/signup"
              variant="outline"
              color="neutral"
              block
              class="mt-3"
              label="Create a free account"
            />
            <p v-else-if="!isSubscribed" class="type-label mt-3 text-dimmed">Your current plan</p>
            <p v-else class="type-label mt-3 text-dimmed">Included in Premium</p>
          </ClientOnly>
        </div>
      </div>

      <!-- The argument -->
      <div class="min-w-0">
        <section aria-labelledby="unlock-heading">
          <h2 id="unlock-heading" class="type-heading text-highlighted">
            What the subscription actually changes
          </h2>
          <p class="type-meta measure mt-2 text-muted">
            Same market, same term, same briefing. The difference is whether you can see the count.
          </p>
          <p class="type-label mt-3 text-dimmed">
            Illustration &mdash; figures below are an example, not live data
          </p>

          <div class="mt-6 grid gap-4 sm:grid-cols-2">
            <!-- Locked -->
            <div class="rounded-sm border border-default bg-default p-5">
              <p class="type-label flex items-center gap-1.5 text-dimmed">
                <UIcon name="i-lucide-lock" class="size-3.5" aria-hidden="true" />
                <span>Without a subscription</span>
              </p>
              <div class="mt-4">
                <UiTermChip term="shutdown" :price="62" size="lg" />
              </div>
              <dl class="mt-4 space-y-2.5">
                <UiStatRow semantic label="Mentions" :value="null" divided />
                <UiStatRow semantic label="Trend" :value="null" divided />
                <UiStatRow semantic label="Quoted context" :value="null" />
              </dl>
              <p class="type-caption mt-4 text-dimmed">
                You get the market and the word. The numbers stay hidden.
              </p>
            </div>

            <!-- Unlocked -->
            <div class="rounded-sm border border-accented bg-elevated/40 p-5">
              <p class="type-label flex items-center gap-1.5 text-mark-600 dark:text-mark-400">
                <UIcon name="i-lucide-lock-open" class="size-3.5" aria-hidden="true" />
                <span>With a subscription</span>
              </p>
              <div class="mt-4">
                <UiTermChip term="shutdown" :price="62" :mentions="14" size="lg" />
              </div>
              <dl class="mt-4 space-y-2.5">
                <UiStatRow semantic label="Mentions" tone="mark" divided>
                  <span class="flex items-center gap-2">
                    <UiTallyRail :count="14" :height="12" />
                    <span>14</span>
                  </span>
                </UiStatRow>
                <UiStatRow semantic label="Trend" value="Rising" tone="yes" icon="i-lucide-trending-up" divided />
                <UiStatRow semantic label="Quoted context" value="9 passages" />
              </dl>
              <p class="type-caption mt-4 text-dimmed">
                Every briefing that said it, how often, and the sentence it sat in.
              </p>
            </div>
          </div>

          <p class="type-caption mt-3 text-dimmed">
            Live figures come from the briefings themselves.
          </p>
        </section>

        <section aria-labelledby="compare-heading" class="mt-12">
          <h2 id="compare-heading" class="type-heading text-highlighted">Free against Premium</h2>

          <div class="mt-5 overflow-x-auto">
            <table class="w-full min-w-[30rem] border-collapse text-left">
              <caption class="sr-only">Features included in the free plan and the premium plan</caption>
              <thead>
                <tr class="border-b border-accented">
                  <th scope="col" class="type-label py-2 pr-4 font-medium text-dimmed">Capability</th>
                  <th scope="col" class="type-label w-20 py-2 text-center font-medium text-dimmed">Free</th>
                  <th scope="col" class="type-label w-24 py-2 text-center font-medium text-dimmed">Premium</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="cap in capabilities" :key="cap.label" class="border-b border-default last:border-0">
                  <th scope="row" class="py-3 pr-4 text-sm font-normal text-default">{{ cap.label }}</th>
                  <td class="py-3 text-center">
                    <UIcon
                      :name="cap.free ? 'i-lucide-check' : 'i-lucide-lock'"
                      class="size-4"
                      :class="cap.free ? 'text-highlighted' : 'text-dimmed'"
                      aria-hidden="true"
                    />
                    <span class="sr-only">{{ cap.free ? 'Included' : 'Not included' }}</span>
                  </td>
                  <td class="py-3 text-center">
                    <UIcon name="i-lucide-check" class="size-4 text-highlighted" aria-hidden="true" />
                    <span class="sr-only">Included</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="faq-heading" class="mt-12">
          <h2 id="faq-heading" class="type-heading text-highlighted">Questions</h2>
          <UAccordion :items="faqItems" class="mt-4" :ui="{ trigger: 'text-base', body: 'text-sm text-muted' }" />
        </section>
      </div>
    </div>
  </div>
</template>
