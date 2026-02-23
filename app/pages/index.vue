<script setup lang="ts">
definePageMeta({ layout: 'saas' })

interface PublicPersona {
  id: string
  name: string
  slug: string | null
  image_url: string | null
  description: string | null
  transcript_count: number
}

const searchQuery = ref('')

const { data: personas, pending } = await useFetch<PublicPersona[]>('/api/public/personas')

useServerSeoMeta({
  title: 'Press Briefing Transcripts for Mentions Market Traders',
  ogTitle: 'Chanis — Press Briefing Transcripts for Market Traders',
  description: 'Browse press briefing transcripts by speaker. Research who gets mentioned in White House briefings for Kalshi and Polymarket mentions markets.',
  ogDescription: 'Browse press briefing transcripts by speaker. Research mentions for prediction market trading on Kalshi and Polymarket.',
  ogType: 'website',
  ogSiteName: 'Chanis',
  twitterCard: 'summary_large_image',
  twitterTitle: 'Chanis — Press Briefing Transcripts',
  twitterDescription: 'Research who gets mentioned in press briefings. Built for Kalshi and Polymarket mentions market traders.',
})

useSchemaOrg([
  defineWebSite({
    name: 'Chanis',
    description: 'Press briefing transcripts for prediction market traders.',
  }),
  defineWebPage({
    name: 'Press Briefing Transcripts Directory',
    description: 'Browse published press briefing transcripts organized by speaker persona.',
  }),
])

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return personas.value ?? []
  return (personas.value ?? []).filter(p =>
    p.name.toLowerCase().includes(q) ||
    p.description?.toLowerCase().includes(q)
  )
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-12">
    <!-- Search -->
    <UInput
      v-model="searchQuery"
      placeholder="Search personas..."
      icon="i-heroicons-magnifying-glass"
      size="lg"
      class="mb-8 max-w-lg mx-auto"
    />

    <!-- Loading -->
    <div v-if="pending" class="flex justify-center py-12">
      <UIcon name="i-heroicons-arrow-path" class="size-8 animate-spin text-gray-400" />
    </div>

    <!-- Empty -->
    <div v-else-if="!filtered.length && !searchQuery.trim()" class="text-center py-12 text-gray-400">
      <UIcon name="i-heroicons-user-group" class="size-12 mx-auto mb-4 opacity-50" />
      <p>No personas published yet.</p>
    </div>

    <!-- No results -->
    <div v-else-if="!filtered.length" class="text-center py-12 text-gray-400">
      <p>No personas matching "{{ searchQuery }}"</p>
    </div>

    <!-- Persona grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink
        v-for="persona in filtered"
        :key="persona.id"
        :to="`/p/${persona.slug}`"
        class="block border border-gray-200 rounded-xl p-4 hover:border-primary transition-colors"
      >
        <div class="flex items-center gap-3 mb-2">
          <img
            v-if="persona.image_url"
            :src="persona.image_url"
            :alt="persona.name"
            class="size-10 rounded-full object-cover"
          />
          <div
            v-else
            class="size-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-sm"
          >
            {{ persona.name[0] }}
          </div>
          <div>
            <div class="font-semibold text-gray-900">{{ persona.name }}</div>
            <div class="text-xs text-gray-400">{{ persona.transcript_count }} transcript{{ persona.transcript_count !== 1 ? 's' : '' }}</div>
          </div>
        </div>
        <p v-if="persona.description" class="text-sm text-gray-500 line-clamp-2">
          {{ persona.description }}
        </p>
      </NuxtLink>
    </div>
  </div>
</template>
