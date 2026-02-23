<script setup lang="ts">
definePageMeta({ layout: 'saas' })

interface Transcript {
  id: string
  name: string | null
  youtube_url: string | null
  upload_date: string | null
  created_at: string
}

interface PersonaDetail {
  id: string
  name: string
  slug: string | null
  image_url: string | null
  description: string | null
  transcripts: Transcript[]
}

const route = useRoute()
const slug = route.params.slug as string

const { data: persona, pending, error } = await useFetch<PersonaDetail>(
  `/api/public/personas/${slug}`
)

const searchQuery = ref('')
const sortOrder = ref<'newest' | 'oldest'>('newest')

function parseDate(t: Transcript): Date {
  if (t.upload_date) {
    const y = t.upload_date.slice(0, 4)
    const m = t.upload_date.slice(4, 6)
    const d = t.upload_date.slice(6, 8)
    return new Date(`${y}-${m}-${d}`)
  }
  return new Date(t.created_at)
}

const filteredTranscripts = computed(() => {
  if (!persona.value) return []
  let list = [...persona.value.transcripts]

  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(t =>
      (t.name || '').toLowerCase().includes(q)
    )
  }

  list.sort((a, b) => {
    const diff = parseDate(b).getTime() - parseDate(a).getTime()
    return sortOrder.value === 'newest' ? diff : -diff
  })

  return list
})

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

function formatUploadDate(dateStr: string) {
  const year = dateStr.slice(0, 4)
  const month = dateStr.slice(4, 6)
  const day = dateStr.slice(6, 8)
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

useHead({
  title: computed(() => persona.value?.name
    ? `${persona.value.name} — Press Briefing Transcripts`
    : 'Persona'),
})

useServerSeoMeta({
  description: computed(() => {
    const p = persona.value
    if (!p) return ''
    const desc = p.description || `Press briefing transcripts featuring ${p.name}.`
    const count = p.transcripts.length
    return `${desc} ${count} transcript${count !== 1 ? 's' : ''} available. Research mentions for prediction market trading.`
  }),
  ogTitle: computed(() => persona.value?.name
    ? `${persona.value.name} — Chanis`
    : 'Persona'),
  ogDescription: computed(() => {
    const p = persona.value
    if (!p) return ''
    return p.description || `Transcripts featuring ${p.name} from press briefings.`
  }),
  ogType: 'profile',
  ogImage: computed(() => persona.value?.image_url || ''),
  ogSiteName: 'Chanis',
  twitterCard: 'summary',
  twitterTitle: computed(() => persona.value?.name
    ? `${persona.value.name} — Chanis`
    : 'Persona'),
  twitterDescription: computed(() => {
    const p = persona.value
    if (!p) return ''
    return p.description || `Transcripts featuring ${p.name}.`
  }),
  twitterImage: computed(() => persona.value?.image_url || ''),
})

useSchemaOrg([
  definePerson({
    name: computed(() => persona.value?.name || ''),
    description: computed(() => persona.value?.description || ''),
    image: computed(() => persona.value?.image_url || ''),
  }),
])
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <!-- Back -->
    <NuxtLink
      to="/"
      class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6"
    >
      <UIcon name="i-heroicons-chevron-left" class="size-4" />
      All personas
    </NuxtLink>

    <!-- Loading -->
    <div v-if="pending && !persona" class="flex justify-center py-20">
      <UIcon name="i-heroicons-arrow-path" class="size-8 animate-spin text-gray-400" />
    </div>

    <!-- Error -->
    <div v-else-if="error || !persona" class="flex flex-col items-center py-20 text-center">
      <UIcon name="i-heroicons-user" class="size-12 text-gray-300 mb-4" />
      <h1 class="text-xl font-semibold text-gray-700 mb-2">Persona not found</h1>
      <p class="text-sm text-gray-500">This persona may not exist or hasn't been published yet.</p>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Persona header -->
      <div class="flex items-start gap-4 mb-8">
        <img
          v-if="persona.image_url"
          :src="persona.image_url"
          :alt="persona.name"
          class="size-16 rounded-full object-cover"
        />
        <div
          v-else
          class="size-16 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xl shrink-0"
        >
          {{ persona.name[0] }}
        </div>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ persona.name }}</h1>
          <p v-if="persona.description" class="text-gray-500 mt-1">{{ persona.description }}</p>
          <p class="text-sm text-gray-400 mt-1">
            {{ persona.transcripts.length }} transcript{{ persona.transcripts.length !== 1 ? 's' : '' }}
          </p>
        </div>
      </div>

      <!-- Search & Sort -->
      <div v-if="persona.transcripts.length" class="flex items-center gap-3 mb-4">
        <UInput
          v-model="searchQuery"
          placeholder="Search transcripts..."
          icon="i-heroicons-magnifying-glass"
          class="flex-1"
        />
        <UButton
          :icon="sortOrder === 'newest' ? 'i-heroicons-bars-arrow-down' : 'i-heroicons-bars-arrow-up'"
          variant="soft"
          size="sm"
          @click="sortOrder = sortOrder === 'newest' ? 'oldest' : 'newest'"
        >
          {{ sortOrder === 'newest' ? 'Newest' : 'Oldest' }}
        </UButton>
      </div>

      <!-- Transcript list -->
      <div v-if="filteredTranscripts.length" class="space-y-3">
        <NuxtLink
          v-for="transcript in filteredTranscripts"
          :key="transcript.id"
          :to="`/view/${transcript.id}`"
          class="flex items-center justify-between border border-gray-200 rounded-lg p-4 hover:border-primary transition-colors"
        >
          <div>
            <div class="font-medium text-gray-900">{{ transcript.name || 'Untitled Transcript' }}</div>
            <div class="text-sm text-gray-400 mt-0.5">
              <template v-if="transcript.upload_date">
                {{ formatUploadDate(transcript.upload_date) }}
              </template>
              <template v-else>
                {{ formatDate(transcript.created_at) }}
              </template>
            </div>
          </div>
          <UButton size="sm" variant="soft">Read</UButton>
        </NuxtLink>
      </div>

      <!-- No search results -->
      <div v-else-if="searchQuery.trim() && persona.transcripts.length" class="text-center py-12 text-gray-400">
        <p>No transcripts matching "{{ searchQuery }}"</p>
      </div>

      <div v-else class="text-center py-12 text-gray-400">
        <p>No transcripts available yet.</p>
      </div>
    </template>
  </div>
</template>
