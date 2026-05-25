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
  AUDIENCE_TYPE_VALUES,
} = useTranscriptMetadata()
const { fetchPersonas, personas } = usePersonas()

const eventTag = ref<EventTag | null>(null)
const contextWindow = ref<ContextWindow | null>(null)
const loading = ref(true)
const editOpen = ref(false)
const saving = ref(false)
const draft = ref<EventTagPatch>({})

const personaId = computed(() => {
  // Default to the Trump persona (matches the backend scheduler pattern)
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
    audience_type: eventTag.value?.audience_type ?? null,
    event_time_local: eventTag.value?.event_time_local ?? null,
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

function formatEventTime(iso: string | null | undefined): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    })
  } catch {
    return iso
  }
}

const locationLabel = computed(() => {
  if (!eventTag.value) return null
  const parts = [eventTag.value.city, eventTag.value.state, eventTag.value.country]
    .filter(Boolean)
  return parts.length ? parts.join(', ') : null
})

const sourceLabel = computed(() => {
  switch (eventTag.value?.classification_source) {
    case 'auto_llm':
      return 'Auto-extracted (LLM suggestion — please verify)'
    case 'auto_ddgs':
      return 'Auto-tagged (keyword classifier)'
    case 'manual':
      return 'Manually confirmed'
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

    <div v-else class="space-y-4">
      <div v-if="!eventTag" class="text-sm text-gray-500">
        No metadata recorded yet. Click "Add metadata" to fill it in.
      </div>

      <template v-else>
        <div v-if="sourceLabel" class="text-xs text-gray-500 italic">
          {{ sourceLabel }}
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <span class="text-gray-500">Type:</span>
            <UBadge v-if="eventTag.event_type" color="primary" variant="subtle" class="ml-2">
              {{ eventTag.event_type.replace(/_/g, ' ') }}
            </UBadge>
          </div>
          <div v-if="eventTag.audience_type">
            <span class="text-gray-500">Audience:</span>
            <UBadge color="neutral" variant="subtle" class="ml-2">
              {{ eventTag.audience_type }}
            </UBadge>
          </div>
          <div v-if="locationLabel">
            <span class="text-gray-500">Location:</span>
            <span class="ml-2 font-medium">{{ locationLabel }}</span>
          </div>
          <div v-if="eventTag.venue">
            <span class="text-gray-500">Venue:</span>
            <span class="ml-2 font-medium">{{ eventTag.venue }}</span>
          </div>
          <div v-if="eventTag.event_time">
            <span class="text-gray-500">Event time:</span>
            <span class="ml-2">{{ formatEventTime(eventTag.event_time) }}</span>
          </div>
          <div v-if="eventTag.event_time_local">
            <span class="text-gray-500">Local time:</span>
            <span class="ml-2">{{ eventTag.event_time_local }}</span>
          </div>
        </div>

        <UDivider v-if="contextWindow" />

        <div v-if="contextWindow" class="space-y-2">
          <div class="flex items-center gap-2 text-sm font-semibold">
            <UIcon name="i-lucide-newspaper" class="size-4" />
            Pre-speech atmosphere
            <span class="text-xs text-gray-500 font-normal">
              ({{ formatEventTime(contextWindow.window_start) }} –
              {{ formatEventTime(contextWindow.window_end) }})
            </span>
          </div>
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div class="text-2xl font-semibold">{{ contextWindow.news_item_count }}</div>
              <div class="text-xs text-gray-500">News items in window</div>
            </div>
            <div>
              <div class="text-2xl font-semibold">{{ contextWindow.truth_social_post_count }}</div>
              <div class="text-xs text-gray-500">Truth Social posts in window</div>
            </div>
          </div>
          <div v-if="contextWindow.top_news_topics?.length" class="flex flex-wrap gap-1">
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
          <UFormField label="Audience">
            <USelectMenu
              v-model="draft.audience_type"
              :items="AUDIENCE_TYPE_VALUES"
              placeholder="Choose audience type"
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
          <UFormField label="Local event time (HH:MM)">
            <UInput v-model="draft.event_time_local" placeholder="e.g. 14:30" />
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
