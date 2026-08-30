<script setup lang="ts">
/**
 * FilterToggle — a segmented filter group with a real accessible contract.
 *
 * Replaces three copies that conveyed selection through button `variant` alone,
 * with no aria-pressed and no group label. Every instance MUST pass `label`:
 * it names the group for screen readers ("Source", "Status", "Sort by").
 *
 * v-model carries the selected value.
 */
const props = withDefaults(defineProps<{
  /** Selected value. Use with v-model. */
  modelValue: string
  /** The options. `count` renders as a mono figure after the label. */
  items: Array<{ label: string, value: string, icon?: string, count?: number | null }>
  /** Names the group. Required. Rendered visually unless `hideLabel`. */
  label: string
  /** Hide the visible label but keep it for assistive tech. */
  hideLabel?: boolean
  size?: 'xs' | 'sm' | 'md'
}>(), {
  hideLabel: false,
  size: 'sm'
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const pad = computed(() => ({
  xs: 'px-2 py-1 text-xs',
  sm: 'px-2.5 py-1.5 text-sm',
  md: 'px-3 py-2 text-sm'
}[props.size]))
</script>

<template>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
    <span class="type-label text-dimmed" :class="hideLabel ? 'sr-only' : ''">{{ label }}</span>

    <div
      role="group"
      :aria-label="label"
      class="inline-flex items-center gap-0.5 rounded-sm border border-default bg-elevated/50 p-0.5"
    >
      <button
        v-for="item in items"
        :key="item.value"
        type="button"
        :aria-pressed="modelValue === item.value"
        class="inline-flex items-center gap-1.5 rounded-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        :class="[
          pad,
          modelValue === item.value
            ? 'bg-inverted text-inverted'
            : 'text-muted hover:bg-accented/60 hover:text-default'
        ]"
        @click="emit('update:modelValue', item.value)"
      >
        <UIcon v-if="item.icon" :name="item.icon" class="size-4" aria-hidden="true" />
        <span>{{ item.label }}</span>
        <span
          v-if="item.count !== null && item.count !== undefined"
          class="type-figure text-xs opacity-60"
        >{{ item.count }}</span>
      </button>
    </div>
  </div>
</template>
