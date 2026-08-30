<script setup lang="ts">
interface Persona {
  id: string
  name: string
  description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

// SSR-compatible fetch (so Google sees the speaker grid content).
// Data contract unchanged: the same call, the same fields.
const { data: personas, status, error, refresh } = await useFetch<Persona[]>('/api/public/personas')

const loading = computed(() => status.value === 'pending')
// A 500 used to render as "No speakers available". It now says what happened.
const failed = computed(() => status.value === 'error' || !!error.value)

// Subscription state is hydrated once by app/plugins/session.client.ts, so the
// paywall prompt no longer shows itself to people who already pay for it.
const { isSubscribed } = useSubscription()

const search = ref('')

const total = computed(() => personas.value?.length ?? 0)

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return personas.value || []
  return (personas.value || []).filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q)
  )
})

// Aliases are the other names a speaker is known by. They are the fastest way to
// confirm you have found the right person, so the card shows the first few.
const ALIAS_LIMIT = 3
const shownAliases = (p: Persona) => (p.aliases || []).slice(0, ALIAS_LIMIT)
const hiddenAliases = (p: Persona) => Math.max(0, (p.aliases?.length || 0) - ALIAS_LIMIT)

const requestMailto = 'mailto:support@mentionshero.com?subject=Transcript%20Request'

// SEO meta tags
useSeoMeta({
  title: 'Transcripts & Mentions Analysis',
  description: 'Browse transcripts of interviews, press briefings, podcasts, and more by speaker. Track what public figures say with full transcript search to help with Kalshi & Polymarket mentions prediction markets.',
  ogTitle: 'MentionsHero — Video Transcripts & Mentions Analysis',
  ogDescription: 'Browse transcripts of interviews, press briefings, podcasts, and more by speaker. Track mentions with full transcript search and analysis.',
  twitterCard: 'summary_large_image',
  twitterTitle: 'MentionsHero — Video Transcripts & Mentions Analysis',
  twitterDescription: 'Browse transcripts of interviews, press briefings, podcasts, and more by speaker. Track mentions with full transcript search and analysis.',
})

defineOgImage({ component: 'OgImageDefault', alt: 'MentionsHero — Video Transcripts & Mentions Analysis' })

// Structured data (Organization + WebSite live in the default layout)
useSchemaOrg([
  defineWebPage({
    name: 'Transcripts & Mentions Analysis',
  }),
])
</script>

<template>
  <div class="pb-20">
    <!-- ================= HERO =================
         The thesis, and the pipeline that backs it: a word -> a count -> a price. -->
    <section class="border-b border-default py-12 sm:py-16">
      <div class="grid gap-12 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:gap-16">
        <div>
          <p class="type-label text-dimmed">A word &middot; a count &middot; a price</p>

          <h1 class="type-title sm:type-display mt-4 measure-wide text-highlighted">
            Count what they <span class="mark-hl">say</span>. Then look at the price.
          </h1>

          <p class="measure mt-6 text-base text-toned">
            MentionsHero transcribes briefings, interviews and podcasts in full, counts how often each
            tracked word is actually spoken, and sets that count beside the Kalshi and Polymarket
            contracts written on the same word.
          </p>

          <div class="mt-8 flex flex-wrap items-center gap-3">
            <UButton to="/markets" size="lg" trailing-icon="i-lucide-arrow-right" label="See the markets" />
            <UButton
              to="#speakers"
              size="lg"
              color="neutral"
              variant="outline"
              icon="i-lucide-user-search"
              label="All speakers"
            />
          </div>

          <p v-if="total" class="mt-6 type-figure text-sm text-dimmed">
            {{ total }} speakers tracked &middot; every word searchable
          </p>
        </div>

        <!-- The mechanism, hung in the margin on large screens. This is genuinely
             a sequence, which is the only reason it carries step numbers. -->
        <ol class="border-t border-default lg:border-l lg:border-t-0 lg:pl-6">
          <li class="rule-dotted py-4 lg:py-5">
            <p class="type-label text-dimmed">01 &mdash; Transcribe</p>
            <p class="mt-2 text-sm text-toned">
              Every briefing, interview and podcast is transcribed in full, with each speaker labelled.
            </p>
          </li>
          <li class="rule-dotted py-4 lg:py-5">
            <p class="type-label text-dimmed">02 &mdash; Count</p>
            <p class="mt-2 text-sm text-toned">
              Search a term across a speaker's whole archive &mdash; say
              <UiTermChip term="shutdown" variant="bare" size="sm" /> &mdash; and see how
              often they really said it.
            </p>
          </li>
          <li class="py-4 lg:py-5">
            <p class="type-label text-dimmed">03 &mdash; Compare</p>
            <p class="mt-2 text-sm text-toned">
              Put that count next to the contract priced on the same word, on Kalshi and Polymarket.
            </p>
          </li>
        </ol>
      </div>
    </section>

    <!-- Paywall prompt. Client-only because the gate depends on the hydrated
         session; subscribers never see it. Premium reads as ink, never amber. -->
    <ClientOnly>
      <UiUpsellBanner
        v-if="!isSubscribed"
        class="mt-10"
        title="Mention counts are part of the subscription"
        description="Subscribe to see how often each term was said, how the count moved across briefings, and the quoted line it came from."
        cta-label="See pricing"
        cta-to="/pricing"
      />
    </ClientOnly>

    <!-- ================= SPEAKERS ================= -->
    <section id="speakers" class="scroll-mt-20 pt-12">
      <div class="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 class="type-heading text-highlighted">Speakers</h2>
          <p class="mt-1 text-sm text-muted">
            Open a speaker to read their transcripts and search every word they said.
          </p>
        </div>

        <UFormField
          label="Find a speaker"
          name="speaker-search"
          :ui="{ label: 'type-label text-dimmed' }"
          class="w-full sm:w-72"
        >
          <UInput
            v-model="search"
            icon="i-lucide-search"
            placeholder="Name or role"
            autocomplete="off"
            class="w-full"
          >
            <template v-if="search" #trailing>
              <UButton
                color="neutral"
                variant="link"
                size="xs"
                icon="i-lucide-x"
                aria-label="Clear the speaker search"
                @click="search = ''"
              />
            </template>
          </UInput>
        </UFormField>
      </div>

      <p v-if="search && !loading && !failed" class="mt-4 type-figure text-sm text-dimmed" aria-live="polite">
        {{ filtered.length }} of {{ total }} speakers
      </p>

      <div class="mt-6">
        <UAlert
          v-if="failed"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          title="The speaker list did not load"
          description="The request to our API failed, so the grid below is empty. Reload it, or try again in a minute."
        >
          <template #actions>
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-rotate-cw"
              label="Try again"
              @click="refresh()"
            />
          </template>
        </UAlert>

        <UiLoadingBlock
          v-else-if="loading"
          variant="cards"
          :count="6"
          :columns="3"
          label="Loading speakers"
        />

        <UiEmptyState
          v-else-if="search && filtered.length === 0"
          icon="i-lucide-search-x"
          :title="`No speaker matches “${search}”`"
          description="Try a shorter word, or clear the search to see everyone we transcribe."
        >
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-x"
            label="Clear the search"
            @click="search = ''"
          />
        </UiEmptyState>

        <UiEmptyState
          v-else-if="filtered.length === 0"
          icon="i-lucide-users"
          title="No speakers are published yet"
          description="Tell us who you are trading and we will start transcribing them."
          action-label="Request a speaker"
          :action-to="requestMailto"
          action-icon="i-lucide-mail"
        />

        <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NuxtLink
            v-for="persona in filtered"
            :key="persona.id"
            :to="`/personas/${persona.slug || persona.id}`"
            class="group block rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <UCard
              class="h-full transition-colors group-hover:bg-elevated/50"
              :ui="{ body: 'p-4 sm:p-5' }"
            >
              <div class="flex items-start gap-4">
                <UiPersonaAvatar :name="persona.name" :src="persona.image_url" size="lg" decorative />
                <div class="min-w-0 flex-1">
                  <p class="type-subhead truncate text-highlighted group-hover:underline underline-offset-4">
                    {{ persona.name }}
                  </p>
                  <p v-if="persona.description" class="mt-1 line-clamp-2 text-sm text-muted">
                    {{ persona.description }}
                  </p>
                </div>
              </div>

              <div v-if="persona.aliases?.length" class="mt-4 border-t border-muted pt-3">
                <p class="type-label text-dimmed">Also called</p>
                <p class="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span
                    v-for="alias in shownAliases(persona)"
                    :key="alias"
                    class="font-mono text-xs text-toned"
                  >{{ alias }}</span>
                  <span v-if="hiddenAliases(persona)" class="font-mono text-xs text-dimmed">
                    +{{ hiddenAliases(persona) }}
                  </span>
                </p>
              </div>
            </UCard>
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- ================= REQUEST ================= -->
    <section class="mt-14 flex flex-col gap-4 rounded-sm border border-default p-5 sm:flex-row sm:items-center sm:p-6">
      <div class="min-w-0 flex-1">
        <p class="font-semibold text-highlighted">We add speakers every week</p>
        <p class="measure mt-1 text-sm text-muted">
          Missing someone the markets price? Write to
          <ULink :to="requestMailto" class="text-default underline underline-offset-4">support@mentionshero.com</ULink>
          and tell us who to start transcribing.
        </p>
      </div>
      <UButton
        :to="requestMailto"
        icon="i-lucide-mail"
        color="neutral"
        variant="outline"
        label="Request a speaker"
        class="shrink-0"
      />
    </section>
  </div>
</template>
