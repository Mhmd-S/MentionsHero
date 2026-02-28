<script setup lang="ts">
const route = useRoute()
const slug = route.params.slug as string
const { publicFetch } = usePublicApi()

interface Persona {
  id: string
  name: string
  description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

interface TranscriptSummary {
  id: string
  name: string | null
  created_at: string
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

const persona = ref<Persona | null>(null)
const transcripts = ref<TranscriptSummary[]>([])
const loadingPersona = ref(true)
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

async function loadPersona() {
  loadingPersona.value = true
  try {
    persona.value = await publicFetch<Persona>(`/api/public/personas/${slug}`)
  } catch {
    persona.value = null
  } finally {
    loadingPersona.value = false
  }
}

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

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

onMounted(async () => {
  await loadPersona()
  await loadTranscripts()
})
</script>

<template>
  <div>
    <!-- Back -->
    <NuxtLink
      to="/"
      class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-6"
    >
      <UIcon name="i-heroicons-chevron-left" class="size-5" />
      <span class="text-sm">All Personas</span>
    </NuxtLink>

    <!-- Loading -->
    <div v-if="loadingPersona" class="flex justify-center py-12">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <!-- Not found -->
    <div v-else-if="!persona" class="py-12 text-center text-gray-500">
      <p>Persona not found.</p>
    </div>

    <template v-else>
      <!-- Persona Header -->
      <div class="flex items-start gap-5 mb-8">
        <div
          v-if="persona.image_url"
          class="w-20 h-20 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden shrink-0"
        >
          <img :src="persona.image_url" :alt="persona.name" class="w-full h-full object-cover" />
        </div>
        <div
          v-else
          class="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center shrink-0"
        >
          <span class="text-2xl font-bold text-primary">{{ persona.name[0] }}</span>
        </div>

        <div>
          <h1 class="text-3xl font-bold mb-1">{{ persona.name }}</h1>
          <p v-if="persona.description" class="text-gray-500">{{ persona.description }}</p>
        </div>
      </div>

      <!-- Transcripts Section -->
      <div class="space-y-4">
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <h2 class="text-xl font-semibold">
            Transcripts
            <span v-if="total > 0" class="text-gray-400 text-base font-normal">({{ total }})</span>
          </h2>

          <div class="flex items-center gap-3">
            <UInput
              v-model="search"
              icon="i-heroicons-magnifying-glass"
              placeholder="Search transcripts..."
              class="w-64"
              size="sm"
            />

            <div class="flex items-center gap-1">
              <UButton
                size="xs"
                :variant="sortBy === 'date' ? 'solid' : 'ghost'"
                @click="toggleSort('date')"
              >
                Date
                <UIcon
                  v-if="sortBy === 'date'"
                  :name="sortOrder === 'desc' ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-up'"
                  class="size-3"
                />
              </UButton>
              <UButton
                size="xs"
                :variant="sortBy === 'name' ? 'solid' : 'ghost'"
                @click="toggleSort('name')"
              >
                Name
                <UIcon
                  v-if="sortBy === 'name'"
                  :name="sortOrder === 'desc' ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-up'"
                  class="size-3"
                />
              </UButton>
            </div>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loadingTranscripts" class="flex justify-center py-8">
          <UIcon name="i-heroicons-arrow-path" class="size-5 animate-spin" />
        </div>

        <!-- Empty -->
        <div v-else-if="transcripts.length === 0" class="py-8 text-center text-gray-500">
          <UIcon name="i-heroicons-document-text" class="size-10 mx-auto mb-3 opacity-50" />
          <p>{{ debouncedSearch ? `No transcripts matching "${debouncedSearch}"` : 'No public transcripts available for this persona' }}</p>
        </div>

        <!-- Transcript List -->
        <div v-else class="divide-y divide-gray-100 dark:divide-gray-800">
          <NuxtLink
            v-for="t in transcripts"
            :key="t.id"
            :to="`/transcripts/${t.id}`"
            class="flex items-start gap-3 py-3 px-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
          >
            <UIcon name="i-heroicons-document-text" class="size-5 text-gray-400 shrink-0 mt-0.5" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium text-sm truncate">{{ t.name || 'Untitled' }}</span>
                <UBadge v-if="t.is_premium" color="warning" variant="subtle" size="xs">Premium</UBadge>
              </div>
              <p v-if="t.preview" class="text-xs text-gray-400 truncate mt-0.5">{{ t.preview }}</p>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[11px] text-gray-400">{{ formatDate(t.created_at) }}</span>
                <template v-if="t.folder_name">
                  <span class="text-gray-300 dark:text-gray-600">&middot;</span>
                  <span class="text-[11px] text-gray-400">{{ t.folder_name }}</span>
                </template>
              </div>
            </div>
          </NuxtLink>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-4">
          <UButton
            size="xs"
            variant="ghost"
            :disabled="page <= 1"
            @click="page--"
            icon="i-heroicons-chevron-left"
          />
          <span class="text-sm text-gray-500">Page {{ page }} of {{ totalPages }}</span>
          <UButton
            size="xs"
            variant="ghost"
            :disabled="page >= totalPages"
            @click="page++"
            icon="i-heroicons-chevron-right"
          />
        </div>
      </div>
    </template>
  </div>
</template>
