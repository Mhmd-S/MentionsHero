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

useHead({
  title: computed(() => persona.value?.meta_title || persona.value?.name || 'Persona'),
  meta: [
    { name: 'description', content: computed(() => persona.value?.meta_description || persona.value?.description || '') },
    { name: 'robots', content: 'index, follow' },
  ],
})

onMounted(async () => {
  await loadPersona()
  await loadTranscripts()
})
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loadingPersona" class="flex justify-center py-16">
      <UIcon name="i-ph-circle-notch" class="size-6 animate-spin text-muted" />
    </div>

    <!-- Not found -->
    <div v-else-if="!persona" class="py-16 text-center text-muted">
      <UIcon name="i-ph-warning" class="size-10 mx-auto mb-3 opacity-40" />
      <p class="font-medium">Persona not found.</p>
      <NuxtLink to="/">
        <UButton variant="outline" size="sm" class="mt-4">Back to Browse</UButton>
      </NuxtLink>
    </div>

    <template v-else>
      <!-- Back link (mobile only, at top) -->
      <NuxtLink to="/" class="sm:hidden flex items-center gap-1 mt-3 text-sm text-muted hover:text-default transition-colors -mb-4">
        <UIcon name="i-ph-arrow-left" class="size-4" />
        All Personas
      </NuxtLink>

      <!-- Persona Header -->
      <UPageHeader
        :title="persona.name"
        :description="persona.description || undefined"
        :links="[{ label: 'All Personas', to: '/', icon: 'i-ph-arrow-left', variant: 'ghost' as const, color: 'neutral' as const, size: 'xs' as const }]"
        :ui="{ links: 'hidden sm:flex' }"
      >
        <template #title>
          <div class="flex items-center gap-4">
            <UAvatar
              v-if="persona.image_url"
              :src="persona.image_url"
              :alt="persona.name"
              size="xl"
            />
            <UAvatar
              v-else
              :text="persona.name[0]"
              size="xl"
            />
            <span>{{ persona.name }}</span>
          </div>
        </template>
      </UPageHeader>

      <!-- Transcripts Section -->
      <div class="space-y-4">
        <div class="flex items-center justify-between gap-4 flex-wrap pt-4">
          <h2 class="text-lg font-semibold">
            Transcripts
            <span v-if="total > 0" class="text-muted text-base font-normal">({{ total }})</span>
          </h2>

          <div class="flex items-center gap-3 flex-wrap w-full sm:w-auto">
            <UInput
              v-model="search"
              icon="i-ph-magnifying-glass"
              placeholder="Search transcripts..."
              class="w-full sm:w-64"
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
                  :name="sortOrder === 'desc' ? 'i-ph-caret-down' : 'i-ph-caret-up'"
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
                  :name="sortOrder === 'desc' ? 'i-ph-caret-down' : 'i-ph-caret-up'"
                  class="size-3"
                />
              </UButton>
            </div>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loadingTranscripts" class="flex justify-center py-8">
          <UIcon name="i-ph-circle-notch" class="size-5 animate-spin text-muted" />
        </div>

        <!-- Empty -->
        <div v-else-if="transcripts.length === 0" class="py-10 text-center text-muted">
          <UIcon name="i-ph-file-text" class="size-10 mx-auto mb-3 opacity-40" />
          <p class="text-sm">{{ debouncedSearch ? `No transcripts matching "${debouncedSearch}"` : 'No public transcripts available' }}</p>
        </div>

        <!-- Transcript List -->
        <div v-else class="space-y-1">
          <NuxtLink
            v-for="t in transcripts"
            :key="t.id"
            :to="`/transcripts/${t.id}`"
            class="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-elevated transition-colors group"
          >
            <UIcon name="i-ph-file-text" class="size-4 text-muted shrink-0" />
            <span class="flex-1 min-w-0 text-sm font-medium truncate group-hover:text-primary transition-colors">
              {{ t.name || 'Untitled' }}
            </span>
            <UBadge v-if="t.is_premium" color="warning" variant="subtle" size="xs">Premium</UBadge>
            <span class="text-xs text-muted tabular-nums shrink-0">{{ formatDate(t.created_at) }}</span>
          </NuxtLink>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-4">
          <UButton
            size="xs"
            variant="ghost"
            :disabled="page <= 1"
            icon="i-ph-caret-left"
            @click="page--"
          />
          <span class="text-sm text-muted">Page {{ page }} of {{ totalPages }}</span>
          <UButton
            size="xs"
            variant="ghost"
            :disabled="page >= totalPages"
            icon="i-ph-caret-right"
            @click="page++"
          />
        </div>
      </div>
    </template>
  </div>
</template>
