<script setup lang="ts">
interface Persona {
  id: string
  name: string
  description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

// SSR-compatible fetch (so Google sees the speaker list). Data contract unchanged.
const { data: personas, status, error, refresh } = await useFetch<Persona[]>('/api/public/personas')

const loading = computed(() => status.value === 'pending')
const failed = computed(() => status.value === 'error' || !!error.value)

const { isSubscribed } = useSubscription()

const search = ref('')
const total = computed(() => personas.value?.length ?? 0)

// Aliases are not shown — they are internal plumbing and made every card twice as
// tall for no reader benefit. They are still searched, so typing "Mr. Netanyahu"
// finds the right person.
const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return personas.value || []
  return (personas.value || []).filter(p =>
    p.name.toLowerCase().includes(q)
    || (p.description || '').toLowerCase().includes(q)
    || (p.aliases || []).some(a => a.toLowerCase().includes(q)),
  )
})

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

useSchemaOrg([
  defineWebPage({ name: 'Press Briefing Transcripts & Mentions Analysis' }),
])
</script>

<template>
  <div class="py-12 sm:py-16">
    <!-- One statement, one supporting line. No eyebrow, no numbered rail, no
         twin CTAs — the search box below is the actual thing people came for. -->
    <header class="max-w-2xl">
      <h1 class="text-3xl sm:text-4xl font-semibold tracking-tight text-highlighted">
        What public figures actually said
      </h1>
      <p class="mt-4 text-base text-muted">
        Full transcripts of briefings, interviews and podcasts, searchable word by word —
        next to the Kalshi and Polymarket contracts written on those same words.
      </p>
    </header>

    <!-- Speakers -->
    <section class="mt-12">
      <div class="flex flex-wrap items-baseline justify-between gap-4 pb-4 border-b border-default">
        <h2 class="text-lg font-medium text-highlighted">
          Speakers
          <span v-if="total" class="text-muted font-normal">({{ total }})</span>
        </h2>
        <UInput
          v-model="search"
          icon="i-lucide-search"
          placeholder="Search speakers"
          aria-label="Search speakers"
          class="w-full sm:w-64"
        />
      </div>

      <div v-if="loading" class="py-20 text-center text-muted text-sm">
        Loading speakers…
      </div>

      <UAlert
        v-else-if="failed"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        title="We couldn't load the speakers"
        description="The list is temporarily unavailable."
        :actions="[{ label: 'Try again', color: 'neutral', variant: 'outline', onClick: () => refresh() }]"
        class="mt-8"
      />

      <div v-else-if="!filtered.length" class="py-20 text-center">
        <p class="text-sm text-muted">
          {{ search ? `No speaker matches “${search}”.` : 'No speakers published yet.' }}
        </p>
        <UButton
          v-if="search"
          variant="ghost"
          color="neutral"
          size="sm"
          class="mt-3"
          label="Clear the search"
          @click="search = ''"
        />
      </div>

      <ul v-else class="divide-y divide-default">
        <li v-for="persona in filtered" :key="persona.id">
          <NuxtLink
            :to="`/personas/${persona.slug || persona.id}`"
            class="flex items-center gap-4 py-4 group"
          >
            <UiPersonaAvatar :name="persona.name" :src="persona.image_url" size="sm" decorative />
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-highlighted group-hover:underline">
                {{ persona.name }}
              </span>
              <span v-if="persona.description" class="block truncate text-sm text-muted">
                {{ persona.description }}
              </span>
            </span>
            <UIcon
              name="i-lucide-chevron-right"
              class="size-4 shrink-0 text-dimmed"
              aria-hidden="true"
            />
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- Quiet, and only for people who aren't already paying. -->
    <p v-if="!isSubscribed" class="mt-12 pt-6 border-t border-default text-sm text-muted">
      Mention counts and term search across a speaker's archive are part of the
      subscription. <NuxtLink to="/pricing" class="text-highlighted underline underline-offset-4">See pricing</NuxtLink>.
    </p>

    <p class="mt-4 text-sm text-muted">
      Missing someone? Email
      <a href="mailto:support@mentionshero.com?subject=Transcript%20Request" class="text-highlighted underline underline-offset-4">support@mentionshero.com</a>.
    </p>
  </div>
</template>
