<script setup lang="ts">
/**
 * PersonaAvatar — one image/initial pair for the whole site.
 *
 * Replaces four copies. The initial fallback is decorative and hidden from
 * assistive tech; the accessible name always comes from `name`, so an avatar
 * next to a visible name should be passed `decorative` to avoid saying it twice.
 */
const props = withDefaults(defineProps<{
  /** Persona name. Drives the initial and the accessible name. Required. */
  name: string
  /** persona.image_url. Null/empty falls back to the initial. */
  src?: string | null
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  /** true when a visible label already names the persona beside this avatar. */
  decorative?: boolean
  /** Amber ring — use only to mark an active/selected persona. */
  active?: boolean
}>(), {
  src: null,
  size: 'md',
  decorative: false,
  active: false
})

const box = computed(() => ({
  xs: 'size-6',
  sm: 'size-8',
  md: 'size-10',
  lg: 'size-14',
  xl: 'size-20'
}[props.size]))

const type = computed(() => ({
  xs: 'text-xs',
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
  xl: 'type-subhead'
}[props.size]))

const initial = computed(() => (props.name || '?').trim().charAt(0).toUpperCase() || '?')
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
const showImage = computed(() => !!props.src && !failed.value)
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-elevated"
    :class="[box, active ? 'ring-2 ring-mark-500 ring-offset-2 ring-offset-bg' : '']"
  >
    <img
      v-if="showImage"
      :src="src!"
      :alt="decorative ? '' : name"
      class="size-full object-cover"
      loading="lazy"
      decoding="async"
      @error="failed = true"
    >
    <template v-else>
      <span class="font-mono font-semibold text-muted" :class="type" aria-hidden="true">{{ initial }}</span>
      <span v-if="!decorative" class="sr-only">{{ name }}</span>
    </template>
  </span>
</template>
