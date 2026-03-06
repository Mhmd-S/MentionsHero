<script setup lang="ts">
const route = useRoute()
const slug = route.params.slug as string
const { publicFetch } = usePublicApi()

interface Persona {
  id: string
  name: string
  description: string | null
  meta_title: string | null
  meta_description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

interface TranscriptSummary {
  id: string
  name: string | null
  created_at: string
  upload_date: string | null
  is_premium: boolean
  folder_id: string | null
  folder_name: string | null
  preview: string
}

interface PaginatedTranscripts {
  items: TranscriptSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// SSR-compatible fetch for persona data (critical for SEO meta tags)
const { data: persona, status: personaStatus } = await useFetch<Persona>(
  `/api/public/personas/${slug}`,
)
const loadingPersona = computed(() => personaStatus.value === 'pending')

const transcripts = ref<TranscriptSummary[]>([])
const loadingTranscripts = ref(false)
const search = ref('')
const sortBy = ref<'date' | 'name'>('date')
const sortOrder = ref<'desc' | 'asc'>('desc')
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

let searchTimer: ReturnType<typeof setTimeout> | null = null
const debouncedSearch = ref('')

watch(search, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedSearch.value = val
    page.value = 1
  }, 400)
})

async function loadTranscripts() {
  if (!persona.value) return
  loadingTranscripts.value = true
  try {
    const params = new URLSearchParams({
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page: String(page.value),
      page_size: '20',
    })
    if (debouncedSearch.value.trim()) {
      params.set('search', debouncedSearch.value.trim())
    }
    const result = await publicFetch<PaginatedTranscripts>(
      `/api/public/personas/${slug}/transcripts?${params}`
    )
    transcripts.value = result.items
    totalPages.value = result.total_pages
    total.value = result.total
  } catch (err) {
    console.error('Failed to load transcripts:', err)
  } finally {
    loadingTranscripts.value = false
  }
}

watch([debouncedSearch, sortBy, sortOrder, page], () => loadTranscripts())

function toggleSort(field: 'date' | 'name') {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'date' ? 'desc' : 'asc'
  }
}

function formatDate(dateString: string | null, fallback?: string) {
  const str = dateString || fallback
  if (!str) return ''
  // Handle YYYYMMDD format from upload_date
  if (/^\d{8}$/.test(str)) {
    const d = new Date(`${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6)}`)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }
  return new Date(str).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// SEO meta tags (rendered during SSR thanks to useFetch above)
useSeoMeta({
  title: () => persona.value?.meta_title || persona.value?.name || 'Persona',
  description: () => persona.value?.meta_description || persona.value?.description || '',
  ogTitle: () => persona.value?.meta_title || persona.value?.name || 'Persona',
  ogDescription: () => persona.value?.meta_description || persona.value?.description || '',
  ogType: 'profile',
  twitterCard: 'summary',
  twitterTitle: () => persona.value?.meta_title || persona.value?.name || 'Persona',
  twitterDescription: () => persona.value?.meta_description || persona.value?.description || '',
  robots: 'index, follow',
})

defineOgImage({
  component: 'OgImagePersona',
  props: {
    name: () => persona.value?.name || '',
    description: () => persona.value?.description || '',
    imageUrl: () => persona.value?.image_url || '',
  },
})

// Structured data
useSchemaOrg([
  definePerson({
    name: () => persona.value?.name || '',
    description: () => persona.value?.description || '',
    image: () => persona.value?.image_url || '',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Personas', item: '/' },
      { name: () => persona.value?.name || '' },
    ],
  }),
])

onMounted(() => loadTranscripts())
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loadingPersona" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin text-muted" />
    </div>

    <!-- Not found -->
    <div v-else-if="!persona" class="py-16 text-center text-muted">
      <UIcon name="i-lucide-alert-triangle" class="size-10 mx-auto mb-3 opacity-40" />
      <p class="font-medium">Persona not found.</p>
      <NuxtLink to="/">
        <UButton variant="outline" size="sm" class="mt-4">Back to Browse</UButton>
      </NuxtLink>
    </div>

    <template v-else>
      <!-- Back link (mobile only, at top) -->


      <!-- Persona Header -->
      <UPageHeader :title="persona.name" :description="persona.description || undefined"
        :ui="{ links: 'hidden sm:flex' }">
        <template #title>
          <NuxtLink to="/"
            class=" flex items-center gap-1 mb-3 text-sm text-muted hover:text-default transition-colors">
            <UIcon name="i-lucide-arrow-left" class="size-4" />
            All Personas
          </NuxtLink>
          <div class="flex items-center gap-4">
            <UAvatar v-if="persona.image_url" :src="persona.image_url" :alt="persona.name" size="xl" />
            <UAvatar v-else :text="persona.name[0]" size="xl" />
            <span>{{ persona.name }}</span>
          </div>
        </template>
      </UPageHeader>

      <!-- Premium upsell -->
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

      <!-- Transcripts Section -->
      <div class="space-y-4">
        <div class="flex items-center justify-between gap-4 flex-wrap pt-4">
          <h2 class="text-lg font-semibold">
            Transcripts
            <span v-if="total > 0" class="text-muted text-base font-normal">({{ total }})</span>
          </h2>

          <div class="flex items-center gap-3 flex-wrap w-full sm:w-auto">
            <UInput v-model="search" icon="i-lucide-search" placeholder="Search transcripts..." class="w-full sm:w-64"
              size="sm" />

            <div class="flex items-center gap-1">
              <UButton size="xs" :variant="sortBy === 'date' ? 'solid' : 'ghost'" @click="toggleSort('date')">
                Date
                <UIcon v-if="sortBy === 'date'"
                  :name="sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" class="size-3" />
              </UButton>
              <UButton size="xs" :variant="sortBy === 'name' ? 'solid' : 'ghost'" @click="toggleSort('name')">
                Name
                <UIcon v-if="sortBy === 'name'"
                  :name="sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" class="size-3" />
              </UButton>
            </div>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loadingTranscripts" class="flex justify-center py-8">
          <UIcon name="i-lucide-loader" class="size-5 animate-spin text-muted" />
        </div>

        <!-- Empty -->
        <div v-else-if="transcripts.length === 0" class="py-10 text-center text-muted">
          <UIcon name="i-lucide-file-text" class="size-10 mx-auto mb-3 opacity-40" />
          <p class="text-sm">{{ debouncedSearch ? `No transcripts matching "${debouncedSearch}"` : 'No public transcripts available' }}</p>
        </div>

        <!-- Transcript List -->
        <div v-else class="space-y-1">
          <NuxtLink v-for="t in transcripts" :key="t.id" :to="`/transcripts/${t.id}`"
            class="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-elevated transition-colors group">
            <UIcon name="i-lucide-file-text" class="size-4 text-muted shrink-0" />
            <span class="flex-1 min-w-0 text-sm font-medium truncate group-hover:text-primary transition-colors">
              {{ t.name || 'Untitled' }}
            </span>
            <UBadge v-if="t.is_premium" color="warning" variant="subtle" size="xs">Premium</UBadge>
            <span class="text-xs text-muted tabular-nums shrink-0">{{ formatDate(t.upload_date, t.created_at) }}</span>
          </NuxtLink>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-4">
          <UButton size="xs" variant="ghost" :disabled="page <= 1" icon="i-lucide-chevron-left" @click="page--" />
          <span class="text-sm text-muted">Page {{ page }} of {{ totalPages }}</span>
          <UButton size="xs" variant="ghost" :disabled="page >= totalPages" icon="i-lucide-chevron-right"
            @click="page++" />
        </div>
      </div>
    </template>
  </div>
</template>
