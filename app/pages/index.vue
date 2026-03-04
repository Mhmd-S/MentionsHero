<script setup lang="ts">
interface Persona {
  id: string
  name: string
  description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

// SSR-compatible fetch (so Google sees persona grid content)
const { data: personas, status } = await useFetch<Persona[]>('/api/public/personas')
const loading = computed(() => status.value === 'pending')

const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return personas.value || []
  return (personas.value || []).filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q)
  )
})

// SEO meta tags
useSeoMeta({
  title: 'Transcripts & Mentions Analysis',
  description: 'Browse transcripts of interviews, press briefings, podcasts, and more by speaker. Track what public figures say with full transcript search to help with Kalshi & Polymarket mentions prediction markets.',
  ogTitle: 'MentionsHero — Video Transcripts & Mentions Analysis',
  ogDescription: 'Browse transcripts of interviews, press briefings, podcasts, and more by speaker. Track mentions with full transcript search and analysis.',
  ogImage: '/og-default.png',
})

// Structured data
useSchemaOrg([
  defineWebSite({
    name: 'MentionsHero',
    description: 'Search and analyze press briefing transcripts linked to Kalshi mentions prediction markets.',
  }),
  defineWebPage({
    name: 'Press Briefing Transcripts & Mentions Analysis',
  }),
])
</script>

<template>
  <div>
    <UPageHeader title="Browse">
      <template #description>
        <span class="text-sm text-muted">Explore transcripts organized by speaker</span>
      </template>
    </UPageHeader>

    <div
      class="my-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="flex-1">
        <p class="text-sm font-medium">Unlock full access to all transcripts</p>
        <p class="text-sm text-muted mt-0.5">
          Get unlimited transcript access, advanced search, and real-time updates with a premium subscription.
        </p>
      </div>
      <UButton to="/pricing" icon="i-lucide-crown" variant="soft" color="warning" size="sm">
        View Pricing
      </UButton>
    </div>

    <UInput v-model="search" icon="i-lucide-search" placeholder="Search speakers..." class="my-3 max-w-sm" />

    <div v-if="loading" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin text-muted" />
    </div>

    <div v-else-if="filtered.length === 0" class="py-16 text-center text-muted">
      <UIcon name="i-lucide-users" class="size-12 mx-auto mb-4 opacity-40" />
      <p class="text-sm">{{ search ? `No results matching "${search}"` : 'No speakers available' }}</p>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink v-for="persona in filtered" :key="persona.id" :to="`/personas/${persona.slug || persona.id}`">
        <UCard class="h-full hover:ring-primary/50 hover:ring-1 transition-all" :ui="{ body: 'sm:p-4' }">
          <div class="flex items-start gap-3.5">
            <UAvatar v-if="persona.image_url" :src="persona.image_url" :alt="persona.name" size="lg" />
            <UAvatar v-else :text="persona.name[0]" size="lg" />
            <div class="flex-1 min-w-0">
              <p class="font-semibold truncate">{{ persona.name }}</p>
              <p v-if="persona.description" class="text-sm text-muted mt-1 line-clamp-2">
                {{ persona.description }}
              </p>
            </div>
          </div>
        </UCard>
      </NuxtLink>
    </div>

    <div
      class="my-4 rounded-lg border border-primary/20 bg-primary/5 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="flex-1">
        <p class="text-sm font-medium">We're expanding our selection daily</p>
        <p class="text-sm text-muted mt-0.5">
          Don't see a speaker you're looking for? Reach out at
          <a href="mailto:support@mentionshero.com?subject=Transcript%20Request"
            class="text-primary hover:underline">support@mentionshero.com</a>
          and we'll add them.
        </p>
      </div>
      <UButton to="mailto:support@mentionshero.com?subject=Transcript%20Request" icon="i-lucide-mail" variant="soft"
        size="sm">
        Request a Speaker
      </UButton>
    </div>
  </div>
</template>
