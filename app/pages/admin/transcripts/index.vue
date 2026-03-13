<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<template>
  <div>
    <div class="flex items-center justify-between gap-4 flex-wrap mb-4">
      <h1 class="text-2xl font-bold">
        All Transcripts
        <span v-if="filtered.length > 0" class="text-muted text-base font-normal">({{ filtered.length }})</span>
      </h1>

      <div class="flex items-center gap-3 flex-wrap w-full sm:w-auto">
        <UInput
          v-model="searchQuery"
          icon="i-lucide-search"
          placeholder="Search transcripts..."
          class="w-full sm:w-64"
          size="sm"
        />

        <div class="flex items-center gap-1">
          <UButton size="xs" :variant="sortBy === 'date' ? 'solid' : 'ghost'" @click="toggleSort('date')">
            Date
            <UIcon v-if="sortBy === 'date'" :name="sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" class="size-3" />
          </UButton>
          <UButton size="xs" :variant="sortBy === 'name' ? 'solid' : 'ghost'" @click="toggleSort('name')">
            Name
            <UIcon v-if="sortBy === 'name'" :name="sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'" class="size-3" />
          </UButton>
        </div>
      </div>
    </div>

    <div v-if="pending" class="flex justify-center py-8">
      <UIcon name="i-lucide-loader" class="size-5 animate-spin text-muted" />
    </div>

    <div v-else-if="error" class="py-8">
      <UAlert color="error" :title="error.message" />
    </div>

    <div v-else-if="!transcripts?.length" class="py-10 text-center text-muted">
      <UIcon name="i-lucide-file-text" class="size-10 mx-auto mb-3 opacity-40" />
      <p class="text-sm">No transcripts yet</p>
      <UButton to="/admin" variant="link" class="mt-2" size="sm">Create your first transcript</UButton>
    </div>

    <div v-else-if="!sorted.length" class="py-10 text-center text-muted">
      <UIcon name="i-lucide-file-text" class="size-10 mx-auto mb-3 opacity-40" />
      <p class="text-sm">No transcripts matching "{{ searchQuery }}"</p>
    </div>

    <div v-else class="space-y-1">
      <div
        v-for="item in sorted"
        :key="item.id"
        class="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-elevated transition-colors group cursor-pointer"
        @click="navigateTo(`/admin/transcripts/${item.id}`)"
      >
        <UIcon name="i-lucide-file-text" class="size-4 text-muted shrink-0" />
        <span class="flex-1 min-w-0 text-sm font-medium truncate group-hover:text-primary transition-colors">
          {{ item.name || 'Untitled' }}
        </span>

        <div class="flex items-center gap-2 sm:gap-3 shrink-0" @click.stop>
          <USwitch
            :model-value="item.is_public ?? false"
            size="xs"
            label="Public"
            @update:model-value="toggleVisibility(item, 'is_public', $event)"
          />
          <USwitch
            :model-value="item.is_premium ?? false"
            size="xs"
            label="Premium"
            @update:model-value="toggleVisibility(item, 'is_premium', $event)"
          />
        </div>

        <span class="text-xs text-muted tabular-nums shrink-0">{{ formatDate(item.upload_date || item.created_at) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Transcript {
  id: string
  name: string | null
  youtube_url: string
  transcript: string
  is_public?: boolean
  is_premium?: boolean
  created_at: string
  upload_date?: string | null
}

const { authFetch } = useAuthFetch()
const transcripts = ref<Transcript[] | null>(null)
const pending = ref(true)
const error = ref<any>(null)
const searchQuery = ref('')
const sortBy = ref<'date' | 'name'>('date')
const sortOrder = ref<'desc' | 'asc'>('desc')

try {
  transcripts.value = await authFetch<Transcript[]>('/api/transcripts')
} catch (e: any) {
  error.value = e
} finally {
  pending.value = false
}

const filtered = computed(() => {
  if (!transcripts.value) return []
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return transcripts.value
  return transcripts.value.filter(t =>
    (t.name || '').toLowerCase().includes(q) ||
    t.youtube_url.toLowerCase().includes(q)
  )
})

function parseDate(dateString: string): Date {
  if (/^\d{8}$/.test(dateString)) {
    return new Date(`${dateString.slice(0, 4)}-${dateString.slice(4, 6)}-${dateString.slice(6)}`)
  }
  return new Date(dateString)
}

const sorted = computed(() => {
  const items = [...filtered.value]
  const dir = sortOrder.value === 'desc' ? -1 : 1
  if (sortBy.value === 'date') {
    items.sort((a, b) => {
      const da = parseDate(a.upload_date || a.created_at).getTime()
      const db = parseDate(b.upload_date || b.created_at).getTime()
      return (da - db) * dir
    })
  } else {
    items.sort((a, b) => {
      const na = (a.name || '').toLowerCase()
      const nb = (b.name || '').toLowerCase()
      return na.localeCompare(nb) * dir
    })
  }
  return items
})

function toggleSort(field: 'date' | 'name') {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'date' ? 'desc' : 'asc'
  }
}

async function toggleVisibility(item: Transcript, field: 'is_public' | 'is_premium', value: boolean) {
  if (field === 'is_premium' && value && !item.is_public) {
    item.is_public = true
    item.is_premium = true
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: true, is_premium: true },
    }).catch(() => {})
  } else if (field === 'is_public' && !value) {
    item.is_public = false
    item.is_premium = false
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: false, is_premium: false },
    }).catch(() => {})
  } else {
    item[field] = value
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { [field]: value },
    }).catch(() => {})
  }
}

function formatDate(dateString: string) {
  const date = parseDate(dateString)
  const now = new Date()
  const sameYear = date.getFullYear() === now.getFullYear()
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(!sameYear && { year: 'numeric' }),
  })
}
</script>
