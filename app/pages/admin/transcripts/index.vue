<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold">All Transcripts</h1>
      <p class="text-gray-500 mt-1">Browse your previously generated transcripts</p>
    </div>

    <UInput
      v-model="searchQuery"
      icon="i-heroicons-magnifying-glass"
      placeholder="Search by name or URL..."
      class="mb-6 max-w-md"
      :ui="{ icon: { trailing: { pointer: '' } } }"
    >
      <template v-if="searchQuery" #trailing>
        <UButton
          color="gray"
          variant="link"
          icon="i-heroicons-x-mark-20-solid"
          :padded="false"
          @click="searchQuery = ''"
        />
      </template>
    </UInput>

    <div v-if="pending" class="flex justify-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <div v-else-if="error" class="py-8">
      <UAlert color="error" :title="error.message" />
    </div>

    <div v-else-if="!transcripts?.length" class="py-8 text-center text-gray-500">
      <UIcon name="i-heroicons-document-text" class="size-12 mx-auto mb-4 opacity-50" />
      <p>No transcripts yet</p>
      <UButton to="/admin" variant="link" class="mt-2">Create your first transcript</UButton>
    </div>

    <div v-else-if="!filtered.length" class="py-8 text-center text-gray-500">
      <p>No transcripts matching "{{ searchQuery }}"</p>
    </div>

    <div v-else>
      <template v-for="(group, groupIdx) in grouped" :key="group.label">
        <div
          class="text-xs font-semibold text-gray-400 uppercase tracking-wider pb-2 sticky top-0 bg-white dark:bg-gray-900 z-10"
          :class="{ 'pt-6 mt-2 border-t border-gray-100 dark:border-gray-800': groupIdx > 0 }"
        >
          {{ group.label }}
        </div>

        <div class="divide-y divide-gray-100 dark:divide-gray-800">
          <div
            v-for="item in group.items"
            :key="item.id"
            class="flex items-start gap-3 py-3 px-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors group"
            @click="navigateTo(`/admin/transcripts/${item.id}`)"
          >
            <UIcon name="i-heroicons-document-text" class="size-5 text-gray-400 shrink-0 mt-0.5" />

            <div class="flex-1 min-w-0">
              <p class="font-medium text-sm truncate" v-html="highlight(item.name || 'Untitled')" />
              <p
                v-if="item.transcript"
                class="text-xs text-gray-400 truncate mt-0.5"
              >
                {{ getPreviewLine(item.transcript) }}
              </p>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[11px] text-gray-400">{{ formatDate(item.created_at) }}</span>
                <span class="text-gray-300 dark:text-gray-600">&middot;</span>
                <span
                  class="text-[11px] text-gray-400 truncate"
                  v-html="highlight(item.youtube_url)"
                />
              </div>
            </div>

            <div class="hidden group-hover:flex items-center gap-1 shrink-0 mt-0.5">
              <UButton
                size="xs"
                variant="ghost"
                color="gray"
                icon="i-heroicons-arrow-top-right-on-square-20-solid"
                :to="`/admin/transcripts/${item.id}`"
                @click.stop
              />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Transcript {
  id: string
  name: string | null
  youtube_url: string
  transcript: string
  created_at: string
}

const { authFetch } = useAuthFetch()
const transcripts = ref<Transcript[] | null>(null)
const pending = ref(true)
const error = ref<any>(null)
const searchQuery = ref('')

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

interface Group {
  label: string
  items: Transcript[]
}

const grouped = computed<Group[]>(() => {
  const items = filtered.value
  if (!items.length) return []

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 86400000)
  const weekStart = new Date(todayStart.getTime() - 7 * 86400000)
  const monthStart = new Date(todayStart.getTime() - 30 * 86400000)

  const buckets: Record<string, Transcript[]> = {
    Today: [],
    Yesterday: [],
    'This Week': [],
    'This Month': [],
    Older: [],
  }
  const order = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older']

  for (const item of items) {
    const d = new Date(item.created_at)
    if (d >= todayStart) buckets.Today.push(item)
    else if (d >= yesterdayStart) buckets.Yesterday.push(item)
    else if (d >= weekStart) buckets['This Week'].push(item)
    else if (d >= monthStart) buckets['This Month'].push(item)
    else buckets.Older.push(item)
  }

  return order
    .filter(label => buckets[label].length > 0)
    .map(label => ({ label, items: buckets[label] }))
})

function getPreviewLine(transcript: string): string {
  const firstLine = transcript.split('\n').find(l => l.trim().length > 0) || ''
  return firstLine.slice(0, 120)
}

function highlight(text: string): string {
  const q = searchQuery.value.trim()
  if (!q) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const escapedQuery = escapeHtml(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(
    new RegExp(`(${escapedQuery})`, 'gi'),
    '<mark class="bg-yellow-200 dark:bg-yellow-700/60 rounded-sm px-0.5">$1</mark>'
  )
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatDate(dateString: string) {
  const date = new Date(dateString)
  const now = new Date()
  const sameYear = date.getFullYear() === now.getFullYear()
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(!sameYear && { year: 'numeric' }),
  })
}
</script>
