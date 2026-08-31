<script setup lang="ts">
const { isSubscribed, fetchSubscription } = useSubscription()
const { session } = useAuth()

interface TopTerm {
  term: string
  mentions: number
  price: number
}

interface MarketEvent {
  source: 'kalshi' | 'polymarket'
  event_id: string
  event_ticker: string | null
  title: string
  strike_date: string | null
  end_date: string | null
  status: string
  image: string | null
  market_count: number
  top_terms: TopTerm[]
}

interface PersonaWithEvents {
  persona: {
    id: string
    name: string
    slug: string | null
    image_url: string | null
  }
  events: MarketEvent[]
}

const { data: personaMarkets, status, error, refresh } = await useFetch<PersonaWithEvents[]>('/api/public/markets')

const loading = computed(() => status.value === 'pending')
const loadError = computed(() => {
  if (!error.value) return ''
  return (error.value as { data?: { detail?: string } })?.data?.detail || 'The markets service did not respond.'
})

/** The two venues, driven from data — the sections are one loop, not twins. */
const SOURCES = [
  { key: 'kalshi', label: 'Kalshi' },
  { key: 'polymarket', label: 'Polymarket' },
] as const

const search = ref('')
const sourceFilter = ref('all')

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  return (personaMarkets.value || [])
    .map((pm) => {
      let events = pm.events
      if (sourceFilter.value !== 'all') {
        events = events.filter((e) => e.source === sourceFilter.value)
      }
      if (q) {
        events = events.filter(
          (e) =>
            e.title.toLowerCase().includes(q) ||
            e.top_terms.some((t) => t.term.toLowerCase().includes(q))
        )
      }
      return { ...pm, events }
    })
    .filter((pm) => pm.events.length > 0)
})

const sections = computed(() =>
  SOURCES.map((source) => {
    const groups = filtered.value
      .map((pm) => ({ ...pm, events: pm.events.filter((e) => e.source === source.key) }))
      .filter((pm) => pm.events.length > 0)
    return {
      ...source,
      groups,
      eventCount: groups.reduce((sum, pm) => sum + pm.events.length, 0),
    }
  }).filter((section) => section.groups.length > 0)
)

const totalEvents = computed(() =>
  (personaMarkets.value || []).reduce((sum, pm) => sum + pm.events.length, 0)
)

const sourceItems = computed(() => {
  const all = personaMarkets.value || []
  const count = (key: string) =>
    all.reduce((sum, pm) => sum + pm.events.filter((e) => e.source === key).length, 0)
  return [
    { label: 'All', value: 'all', count: totalEvents.value },
    { label: 'Kalshi', value: 'kalshi', count: count('kalshi') },
    { label: 'Polymarket', value: 'polymarket', count: count('polymarket') },
  ]
})

function personaHref(persona: PersonaWithEvents['persona']) {
  return `/markets/${persona.slug || persona.id}`
}

/**
 * There is no public per-event route — /api/public exposes only /markets and
 * /markets/{slug}. Each card therefore addresses its event as an anchor on the
 * persona page, which [slug].vue renders as `id="event-{event_id}"`.
 */
function eventHref(persona: PersonaWithEvents['persona'], event: MarketEvent) {
  return `${personaHref(persona)}#event-${event.event_id}`
}

function eventMentions(event: MarketEvent) {
  return event.top_terms.reduce((sum, t) => sum + (t.mentions || 0), 0)
}

function formatDate(dateString: string | null) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

useSeoMeta({
  title: 'Prediction Markets & Transcript Analysis',
  description: 'Track prediction markets linked to transcript mentions. See how often public figures mention key terms and how it relates to Kalshi & Polymarket prices.',
  ogTitle: 'MentionsHero — Prediction Markets Analysis',
  ogDescription: 'Track prediction markets linked to transcript mentions. See mention frequency, trends, and market prices.',
  twitterCard: 'summary_large_image',
  twitterTitle: 'MentionsHero — Prediction Markets Analysis',
  twitterDescription: 'Track prediction markets linked to transcript mentions. See mention frequency, trends, and market prices.',
  robots: 'index, follow',
})

defineOgImage({ component: 'OgImageDefault', alt: 'MentionsHero — Prediction Markets Analysis' })

onMounted(() => {
  if (session.value) fetchSubscription()
})

useSchemaOrg([
  defineWebPage({
    name: 'Prediction Markets & Transcript Analysis',
    description: 'Track prediction markets linked to transcript mentions across Kalshi and Polymarket.',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: 'Markets' },
    ],
  }),
  {
    '@type': 'FAQPage',
    'mainEntity': [
      {
        '@type': 'Question',
        'name': 'What is a mentions prediction market?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'A mentions prediction market is a binary contract on whether a public figure will say a specific word or phrase during a given event or time period — for example, whether the President says "tariffs" at an upcoming press conference. Traders buy Yes or No shares, and the contract resolves once the event happens and the transcript is available.',
        },
      },
      {
        '@type': 'Question',
        'name': 'Which prediction markets does MentionsHero cover?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'MentionsHero tracks two venues: Kalshi and Polymarket. Kalshi events come from its "Mentions" category, where each market carries the tracked word or phrase. Polymarket events are added by our editors from the Polymarket Gamma API. On this page, Kalshi and Polymarket events are listed in separate sections and grouped by the persona they relate to.',
        },
      },
      {
        '@type': 'Question',
        'name': 'How does MentionsHero count mentions?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'We transcribe press briefings, interviews, podcasts, and other public appearances with speaker diarization, then attribute each line to a persona through that persona\'s known speaker names and aliases. For every market we extract the tracked term, then count case-insensitive whole-word matches in that persona\'s transcripts. We report the total mentions, how many briefings contained the term, the share of briefings that did, and a rising, falling, or stable trend.',
        },
      },
      {
        '@type': 'Question',
        'name': 'Where do the search terms for each market come from?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'The terms come from the market itself, not from us. For Kalshi we use the market\'s custom strike word, and compound strikes such as "Shutdown / Shut Down" are split into separate terms. For Polymarket we use the market\'s group item title, falling back to the quoted phrase in the question text. That keeps our counts aligned with what the contract actually resolves on.',
        },
      },
      {
        '@type': 'Question',
        'name': 'Does a high historical mention rate mean the market is mispriced?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'Not on its own. Historical mention rates describe past appearances and say nothing certain about the next one — venue, topic, and news cycle matter a great deal. MentionsHero shows the evidence, including mention counts, briefing coverage, trend, and the transcript context around each mention, so you can form your own view. It is research, not trading advice.',
        },
      },
      {
        '@type': 'Question',
        'name': 'What can I see for free, and what needs a subscription?',
        'acceptedAnswer': {
          '@type': 'Answer',
          'text': 'Anyone can browse the tracked events, the market questions, the current prices, and how each market resolved. The analysis layer — mention counts, briefings ratio, percentages, trends, and transcript context — requires a premium subscription.',
        },
      },
    ],
  },
])
</script>

<template>
  <div>
    <UPageHeader
      title="Markets"
      :ui="{
        title: 'text-2xl sm:text-2xl text-highlighted',
        description: 'mt-4 measure text-base text-muted',
      }"
    >
      <template #description>
        <span class="text-base text-muted">
          Every word a market prices, counted in the transcripts.
          <span v-if="totalEvents > 0" class="type-figure text-default">{{ totalEvents }}</span>
          <span v-if="totalEvents > 0"> events tracked across Kalshi and Polymarket.</span>
        </span>
      </template>
    </UPageHeader>

    <!-- Filters -->
    <div class="my-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <UInput
        v-model="search"
        type="search"
        icon="i-lucide-search"
        aria-label="Search markets by event title or tracked term"
        placeholder="Search events or terms"
        class="w-full sm:w-80"
        size="md"
        variant="outline"
      />
      <UiFilterToggle v-model="sourceFilter" label="Venue" :items="sourceItems" />
    </div>

    <!-- Loading -->
    <UiLoadingBlock v-if="loading" variant="cards" :count="6" :columns="2" label="Loading markets" />

    <!-- Error -->
    <UAlert
      v-else-if="loadError"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      title="The markets did not load"
      :description="loadError"
      :actions="[{ label: 'Try again', color: 'neutral', variant: 'outline', onClick: () => refresh() }]"
    />

    <!-- Empty -->
    <UiEmptyState
      v-else-if="sections.length === 0"
      icon="i-lucide-chart-bar"
      :title="search ? `Nothing matches \u201c${search}\u201d` : 'No markets are tracked yet'"
      :description="search
        ? 'Try a shorter word, or set the venue filter back to All.'
        : 'Once a Kalshi or Polymarket mentions event is linked to a persona, it appears here with its mention counts.'"
    >
      <UButton
        v-if="search || sourceFilter !== 'all'"
        color="primary"
        variant="solid"
        icon="i-lucide-rotate-cw"
        @click="search = ''; sourceFilter = 'all'"
      >
        Clear the filters
      </UButton>
      <UButton v-else to="/" color="primary" variant="solid" trailing-icon="i-lucide-arrow-right">
        Browse transcripts
      </UButton>
    </UiEmptyState>

    <!-- Venue sections: one loop, both venues, equal treatment -->
    <div v-else class="space-y-12">
      <section v-for="section in sections" :key="section.key">
        <div class="rule-dotted mb-5 flex items-baseline gap-3 pb-2">
          <h2 class="type-heading text-highlighted">{{ section.label }}</h2>
          <UBadge color="neutral" variant="subtle" size="sm" class="type-figure">
            {{ section.eventCount }}
          </UBadge>
          <span class="type-caption text-dimmed">{{ section.eventCount === 1 ? 'event' : 'events' }}</span>
        </div>

        <div class="space-y-8">
          <div v-for="pm in section.groups" :key="pm.persona.id">
            <!-- Persona row -->
            <div class="mb-3 flex items-center gap-3">
              <UiPersonaAvatar :name="pm.persona.name" :src="pm.persona.image_url" size="md" decorative />
              <div class="min-w-0 flex-1">
                <ULink
                  :to="`/personas/${pm.persona.slug || pm.persona.id}`"
                  class="block truncate font-semibold text-highlighted hover:text-primary"
                >
                  {{ pm.persona.name }}
                </ULink>
                <p class="type-caption text-dimmed">
                  <span class="type-figure">{{ pm.events.length }}</span>
                  {{ pm.events.length === 1 ? 'event' : 'events' }} on {{ section.label }}
                </p>
              </div>
              <UButton
                :to="personaHref(pm.persona)"
                variant="outline"
                color="neutral"
                size="xs"
                trailing-icon="i-lucide-arrow-right"
                class="shrink-0"
              >
                All markets
              </UButton>
            </div>

            <!-- Event cards -->
            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <NuxtLink
                v-for="event in pm.events"
                :key="event.event_id"
                :to="eventHref(pm.persona, event)"
                class="group block focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <UCard
                  class="h-full transition-colors group-hover:border-accented group-hover:bg-elevated/40"
                  :ui="{ body: 'sm:p-4' }"
                >
                  <div class="flex items-start gap-3">
                    <img
                      v-if="event.image"
                      :src="event.image"
                      alt=""
                      class="size-10 shrink-0 rounded-sm object-cover"
                    >
                    <div class="min-w-0 flex-1">
                      <div class="flex items-start justify-between gap-2">
                        <p class="text-sm font-medium leading-snug text-highlighted">{{ event.title }}</p>
                        <UBadge
                          v-if="event.status !== 'active'"
                          color="neutral"
                          variant="subtle"
                          size="xs"
                          class="shrink-0 capitalize"
                        >
                          {{ event.status }}
                        </UBadge>
                      </div>

                      <p class="type-caption mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-dimmed">
                        <span v-if="event.strike_date || event.end_date" class="type-figure">
                          {{ formatDate(event.strike_date || event.end_date) }}
                        </span>
                        <span v-if="(event.strike_date || event.end_date) && event.market_count" aria-hidden="true">&middot;</span>
                        <span v-if="event.market_count">
                          <span class="type-figure">{{ event.market_count }}</span>
                          {{ event.market_count === 1 ? 'market' : 'markets' }}
                        </span>
                        <template v-if="eventMentions(event) > 0">
                          <span aria-hidden="true">&middot;</span>
                          <span class="text-mark-600 dark:text-mark-400">
                            <span class="type-figure">{{ eventMentions(event) }}</span>
                            {{ eventMentions(event) === 1 ? 'mention' : 'mentions' }}
                          </span>
                        </template>
                      </p>

                      <div v-if="event.top_terms.length > 0" class="mt-3 flex flex-wrap items-center gap-1.5">
                        <UiTermChip
                          v-for="term in event.top_terms"
                          :key="term.term"
                          :term="term.term"
                          :price="term.price"
                          :mentions="term.mentions"
                          size="sm"
                        />
                        <span
                          v-if="event.market_count > event.top_terms.length"
                          class="type-caption text-dimmed"
                        >
                          +<span class="type-figure">{{ event.market_count - event.top_terms.length }}</span> more
                        </span>
                      </div>
                    </div>
                  </div>
                </UCard>
              </NuxtLink>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Paywall prompt (non-subscribers only) -->
    <UiUpsellBanner
      v-if="!isSubscribed"
      class="mt-10"
      title="Mention counts and trends are part of the subscription"
      description="Subscribe to see how often each term was said, how many briefings it appeared in, and which way the count is moving."
    />
  </div>
</template>
