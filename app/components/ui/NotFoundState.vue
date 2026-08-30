<script setup lang="ts">
/**
 * NotFoundState — the thing at this URL does not exist.
 *
 * Replaces three copies. Always offers a route back into the site; the default
 * is the transcript index. Use inside a page whose data came back empty for a
 * given id/slug. For a real HTTP 404 the app/error.vue page handles it.
 */
withDefaults(defineProps<{
  /** What was not found, e.g. "Persona not found". */
  title?: string
  description?: string | null
  backLabel?: string
  backTo?: string
  icon?: string
}>(), {
  title: 'We could not find that page',
  description: 'It may have been removed, or the address may be wrong.',
  backLabel: 'Back to transcripts',
  backTo: '/',
  icon: 'i-lucide-search-x'
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-4 px-6 py-20 text-center">
    <UIcon :name="icon" class="size-8 text-dimmed" aria-hidden="true" />

    <div class="max-w-md">
      <p class="type-subhead font-semibold text-highlighted">{{ title }}</p>
      <p v-if="description" class="mt-2 text-sm text-muted">{{ description }}</p>
    </div>

    <slot>
      <UButton :to="backTo" :label="backLabel" icon="i-lucide-arrow-left" color="primary" variant="solid" />
    </slot>
  </div>
</template>
