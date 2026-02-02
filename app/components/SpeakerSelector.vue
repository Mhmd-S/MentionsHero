<script setup lang="ts">
export interface SpeakerInfo {
  name: string
  segment_count: number
  briefings: number
}

const props = withDefaults(
  defineProps<{
    modelValue?: string[] | string | null
    folderId?: string | null
    placeholder?: string
  }>(),
  {
    modelValue: null,
    folderId: null,
    placeholder: 'All speakers'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string[] | string | null]
}>()

const speakers = ref<SpeakerInfo[]>([])
const loading = ref(false)

const options = computed(() => [
  ...speakers.value.map((s: SpeakerInfo) => ({
    label: `${s.name} (${s.briefings} briefings)`,
    value: s.name
  }))
])

const selected = computed<string[]>({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue : props.modelValue ? [props.modelValue] : []),
  set: (value: string[] | string) => {
    const normalized = Array.isArray(value) ? value.filter(Boolean) : value ? [value] : []
    emit('update:modelValue', normalized.length > 0 ? normalized : null)
  }
})

const selectionPlaceholder = computed(() =>
  selected.value.length === 0
    ? props.placeholder
    : `${selected.value.length} selected`
)

async function loadSpeakers() {
  loading.value = true
  try {
    const result = await $fetch<{ speakers: SpeakerInfo[] }>('/api/analysis/speakers', {
      query: props.folderId ? { folder_id: props.folderId } : undefined
    })
    speakers.value = result.speakers || []
  } catch (e) {
    console.error('Failed to fetch speakers:', e)
    speakers.value = []
  } finally {
    loading.value = false
  }
}

function removeSpeaker(name: string) {
  const next = selected.value.filter((s) => s !== name)
  emit('update:modelValue', next.length > 0 ? next : null)
}

watch(
  () => props.folderId,
  (id) => {
    if (!id) {
      speakers.value = []
      return
    }
    loadSpeakers()
  },
  { immediate: true }
)
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2">
      <label class="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">Speaker:</label>
      <USelectMenu
        v-model="selected"
        :items="options"
        :loading="loading"
        :disabled="!props.folderId"
        :placeholder="selectionPlaceholder"
        class="w-60"
        multiple
        searchable
        :reset-search-term-on-select="false"
        value-key="value"
        label-key="label"
      >
        <template>
          <span class="truncate">{{ selectionPlaceholder }}</span>
        </template>
      </USelectMenu>
    </div>
    <div v-if="selected.length > 0" class="flex flex-wrap gap-2">
      <UBadge
        v-for="name in selected"
        :key="name"
        color="neutral"
        size="md"
        class="cursor-pointer"
        @click="removeSpeaker(name)"
      >
        {{ name }}
        <UIcon name="i-heroicons-x-mark" class="w-3 h-3 ml-1" />
      </UBadge>
    </div>
  </div>
</template>
