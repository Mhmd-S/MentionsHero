<script setup lang="ts">
/**
 * Date-range trigger form for a scrape. Emits `scrape` with ISO-8601 bounds;
 * the parent panel owns the API call + toasts.
 */
withDefaults(
  defineProps<{ loading?: boolean; submitLabel?: string }>(),
  { loading: false, submitLabel: 'Scrape range' },
)

const emit = defineEmits<{ scrape: [payload: { startDate: string; endDate: string }] }>()

const today = new Date().toISOString().slice(0, 10)
const startDate = ref('2026-01-01')
const endDate = ref(today)

const rangeError = computed(() =>
  startDate.value && endDate.value && endDate.value < startDate.value
    ? 'End date must be on or after start date'
    : '',
)

function submit() {
  if (rangeError.value) return
  emit('scrape', {
    startDate: `${startDate.value}T00:00:00Z`,
    endDate: `${endDate.value}T23:59:59Z`,
  })
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end gap-3">
      <UFormField label="From">
        <UInput v-model="startDate" type="date" />
      </UFormField>
      <UFormField label="To">
        <UInput v-model="endDate" type="date" />
      </UFormField>
      <UButton
        icon="i-lucide-download"
        :loading="loading"
        :disabled="!!rangeError"
        @click="submit"
      >
        {{ submitLabel }}
      </UButton>
    </div>
    <p v-if="rangeError" class="text-xs text-red-500 mt-1">{{ rangeError }}</p>
  </div>
</template>
