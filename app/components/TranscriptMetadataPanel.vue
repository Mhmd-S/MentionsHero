<script setup lang="ts">
import type { EventTag, EventTagPatch, ContextWindow } from '~/composables/useTranscriptMetadata'

const props = defineProps<{
  transcriptId: string
}>()

const {
  getEventTag,
  updateEventTag,
  getContextWindow,
  EVENT_TYPE_VALUES,
} = useTranscriptMetadata()
const { fetchPersonas, personas } = usePersonas()

const eventTag = ref<EventTag | null>(null)
const contextWindow = ref<ContextWindow | null>(null)
const loading = ref(true)
const editOpen = ref(false)
const saving = ref(false)
const draft = ref<EventTagPatch>({})

const personaId = computed(() => {
  return (
    personas.value.find((p) => p.name.toLowerCase().includes('trump'))?.id ||
    personas.value[0]?.id ||
    null
  )
})

async function load() {
  loading.value = true
  try {
    if (personas.value.length === 0) {
      await fetchPersonas()
    }
    eventTag.value = await getEventTag(props.transcriptId)
    if (personaId.value) {
      contextWindow.value = await getContextWindow(props.transcriptId, personaId.value)
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.transcriptId, load)

function openEdit() {
  draft.value = {
    event_type: eventTag.value?.event_type ?? 'other',
    city: eventTag.value?.city ?? null,
    state: eventTag.value?.state ?? null,
    country: eventTag.value?.country ?? null,
    venue: eventTag.value?.venue ?? null,
  }
  editOpen.value = true
}

async function save() {
  saving.value = true
  try {
    const updated = await updateEventTag(props.transcriptId, draft.value)
    if (updated) {
      eventTag.value = updated
    }
    editOpen.value = false
  } finally {
    saving.value = false
  }
}

function formatEventTimeFull(iso: string | null | undefined): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short',
    })
  } catch {
    return iso
  }
}

function formatWindowRange(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  try {
    const opts: Intl.DateTimeFormatOptions = {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }
    return `${new Date(start).toLocaleString('en-US', opts)} – ${new Date(end).toLocaleString('en-US', opts)}`
  } catch {
    return `${start} – ${end}`
  }
}

const locationLabel = computed(() => {
  if (!eventTag.value) return null
  const parts = [eventTag.value.city, eventTag.value.state, eventTag.value.country]
    .filter(Boolean)
  return parts.length ? parts.join(', ') : null
})

const sourceBadge = computed(() => {
  switch (eventTag.value?.classification_source) {
    case 'auto_llm':
      return { label: 'LLM suggestion', color: 'warning' as const, icon: 'i-lucide-sparkles' }
    case 'auto_ddgs':
      return { label: 'Keyword classifier', color: 'neutral' as const, icon: 'i-lucide-search' }
    case 'manual':
      return { label: 'Manually confirmed', color: 'success' as const, icon: 'i-lucide-check-circle' }
    default:
      return null
  }
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-map-pin" class="size-5" />
          <h3 class="font-semibold">Event metadata</h3>
          <UBadge v-if="sourceBadge" :color="sourceBadge.color" variant="subtle" size="xs">
            <UIcon :name="sourceBadge.icon" class="size-3 mr-1" />
            {{ sourceBadge.label }}
          </UBadge>
        </div>
        <UButton
          v-if="eventTag"
          variant="outline"
          size="xs"
          icon="i-lucide-pencil"
          @click="openEdit"
        >
          Edit
        </UButton>
        <UButton
          v-else-if="!loading"
          variant="outline"
          size="xs"
          icon="i-lucide-plus"
          @click="openEdit"
        >
          Add metadata
        </UButton>
      </div>
    </template>

    <div v-if="loading" class="py-6 flex justify-center">
      <UIcon name="i-lucide-loader" class="size-5 animate-spin" />
    </div>

    <div v-else class="space-y-5">
      <div v-if="!eventTag" class="text-sm text-gray-500">
        No metadata recorded yet. Click "Add metadata" to fill it in, or run the
        Backfill from the persona detail page.
      </div>

      <template v-else>
        <!-- Type -->
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs uppercase tracking-wide text-gray-500">Type</span>
          <UBadge color="primary" variant="subtle">
            {{ eventTag.event_type.replace(/_/g, ' ') }}
          </UBadge>
        </div>

        <!-- When -->
        <div v-if="eventTag.event_time" class="space-y-1">
          <div class="text-xs uppercase tracking-wide text-gray-500">When</div>
          <div class="text-sm font-medium">
            {{ formatEventTimeFull(eventTag.event_time) }}
          </div>
        </div>

        <!-- Where -->
        <div v-if="locationLabel || eventTag.venue" class="space-y-1">
          <div class="text-xs uppercase tracking-wide text-gray-500">Where</div>
          <div v-if="eventTag.venue" class="text-sm font-medium">{{ eventTag.venue }}</div>
          <div v-if="locationLabel" class="text-sm text-gray-700 dark:text-gray-300">
            {{ locationLabel }}
          </div>
        </div>

        <!-- Pre-speech atmosphere -->
        <template v-if="contextWindow">
          <UDivider />
          <div class="space-y-2">
            <div class="flex items-center gap-2 text-sm font-semibold">
              <UIcon name="i-lucide-newspaper" class="size-4" />
              Pre-speech atmosphere
              <span class="text-xs text-gray-500 font-normal">
                {{ formatWindowRange(contextWindow.window_start, contextWindow.window_end) }}
              </span>
            </div>
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div class="text-2xl font-semibold tabular-nums">
                  {{ contextWindow.news_item_count }}
                </div>
                <div class="text-xs text-gray-500">News items in window</div>
              </div>
              <div>
                <div class="text-2xl font-semibold tabular-nums">
                  {{ contextWindow.truth_social_post_count }}
                </div>
                <div class="text-xs text-gray-500">Truth Social posts in window</div>
              </div>
            </div>
            <div v-if="contextWindow.top_news_topics?.length" class="flex flex-wrap gap-1 pt-1">
              <span class="text-xs text-gray-500 self-center mr-1">Top news topics:</span>
              <UBadge
                v-for="topic in contextWindow.top_news_topics"
                :key="topic"
                color="neutral"
                variant="soft"
                size="xs"
              >
                {{ topic }}
              </UBadge>
            </div>
          </div>
        </template>
      </template>
    </div>

    <UModal v-model:open="editOpen" title="Edit event metadata">
      <template #body>
        <div class="space-y-4">
          <UFormField label="Event type" required>
            <USelectMenu
              v-model="draft.event_type"
              :items="EVENT_TYPE_VALUES"
              placeholder="Choose event type"
            />
          </UFormField>
          <div class="grid grid-cols-2 gap-3">
            <UFormField label="City">
              <UInput v-model="draft.city" placeholder="e.g. Phoenix" />
            </UFormField>
            <UFormField label="State">
              <UInput v-model="draft.state" placeholder="e.g. Arizona" />
            </UFormField>
          </div>
          <UFormField label="Country">
            <UInput v-model="draft.country" placeholder="e.g. US" />
          </UFormField>
          <UFormField label="Venue">
            <UInput
              v-model="draft.venue"
              placeholder="e.g. Oval Office, The White House"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 w-full">
          <UButton variant="ghost" @click="editOpen = false">Cancel</UButton>
          <UButton :loading="saving" color="primary" @click="save">Save</UButton>
        </div>
      </template>
    </UModal>
  </UCard>
</template>
