<script setup lang="ts">
export interface SpeakerInfo {
  name: string
  segment_count: number
  briefings: number
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | null
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
  'update:modelValue': [value: string | null]
}>()

const speakers = ref<SpeakerInfo[]>([])
const loading = ref(false)

const SPEAKER_ALL = '__all__' as const

const options = computed(() => [
  { label: props.placeholder, value: SPEAKER_ALL },
  ...speakers.value.map((s: SpeakerInfo) => ({
    label: `${s.name} (${s.briefings} briefings)`,
    value: s.name
  }))
])

const selected = computed({
  get: () => props.modelValue ?? SPEAKER_ALL,
  set: (v: string) => emit('update:modelValue', v === SPEAKER_ALL ? null : v)
})

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
  <div class="flex items-center gap-2">
    <label class="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">Speaker:</label>
    <USelect
      v-model="selected"
      :items="options"
      :loading="loading"
      :disabled="!props.folderId"
      class="min-w-[200px]"
      value-key="value"
    />
  </div>
</template>
