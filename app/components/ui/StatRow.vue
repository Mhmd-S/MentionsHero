<script setup lang="ts">
/**
 * StatRow — one label/value line in the mono voice, for metadata lists.
 *
 * The label is a small mono caps label; the value is always mono, because a
 * value in a StatRow is evidence: a count, a date, a price, a ticker.
 *
 * By default it renders neutral <span>s and can sit anywhere. Pass
 * `semantic` when the row lives inside a real <dl> and you want <dt>/<dd>.
 */
const props = withDefaults(defineProps<{
  /** What the value is. Keep it short: "Mentions", "Briefings", "Last said". */
  label: string
  /** The value. Pass a preformatted string for dates and prices. */
  value?: string | number | null
  /** Shown in place of the value when it is null / undefined / ''. */
  fallback?: string
  /** Reserved colours: 'yes'/'no' are market outcome or trend ONLY.
   *  'mark' means a mention happened. */
  tone?: 'default' | 'mark' | 'yes' | 'no' | 'muted'
  /** Optional lucide icon before the label. */
  icon?: string | null
  /** 'row' = label left, value right. 'stack' = label above value (KPI block). */
  layout?: 'row' | 'stack'
  /** Draws a dotted leader rule under the row. */
  divided?: boolean
  size?: 'sm' | 'md' | 'lg'
  /** Render <dt>/<dd>. Only valid inside a <dl>. */
  semantic?: boolean
}>(), {
  value: null,
  fallback: '—',
  tone: 'default',
  icon: null,
  layout: 'row',
  divided: false,
  size: 'md',
  semantic: false
})

const TONES = {
  default: 'text-highlighted',
  mark: 'text-mark-600 dark:text-mark-400',
  yes: 'text-success',
  no: 'text-error',
  muted: 'text-muted'
} as const

const labelTag = computed(() => (props.semantic ? 'dt' : 'span'))
const valueTag = computed(() => (props.semantic ? 'dd' : 'span'))
const toneClass = computed(() => TONES[props.tone])
const sizeClass = computed(() => (props.size === 'lg' ? 'text-xl' : props.size === 'sm' ? 'text-sm' : 'text-base'))
const isEmpty = computed(() => props.value === null || props.value === undefined || props.value === '')
</script>

<template>
  <div
    :class="[
      layout === 'row' ? 'flex items-baseline justify-between gap-4' : 'flex flex-col gap-1',
      divided ? 'rule-dotted pb-2' : ''
    ]"
  >
    <component :is="labelTag" class="type-label flex items-center gap-1.5 text-dimmed">
      <UIcon v-if="icon" :name="icon" class="size-3.5" aria-hidden="true" />
      <span>{{ label }}</span>
    </component>

    <component :is="valueTag" class="type-figure m-0" :class="[toneClass, sizeClass]">
      <slot>{{ isEmpty ? fallback : value }}</slot>
    </component>
  </div>
</template>
