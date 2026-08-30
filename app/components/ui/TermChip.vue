<script setup lang="ts">
/**
 * TermChip — the product's visual atom.
 *
 * A tracked term in real typographic quotes, mono, with its market price sitting
 * in the same object. Word and price belong together: that pairing IS the product.
 *
 * Public API prices (`/api/public/markets*`) arrive as integers 0–100, so the
 * default `priceUnit` is 'cents'. Raw Polymarket values are 0–1 decimals:
 * pass priceUnit="fraction".
 */
const props = withDefaults(defineProps<{
  /** The tracked search term. Rendered inside “ ” in mono. */
  term: string
  /** Market price. Omit or pass null to render the term alone. */
  price?: number | null
  /** How to read `price`. 'cents' = 0–100, 'fraction' = 0–1. */
  priceUnit?: 'cents' | 'fraction'
  /** Mention count. Renders a small tally rail beside the term when > 0. */
  mentions?: number | null
  /** Market outcome when resolved ('yes' | 'no'). Colours the price. */
  result?: string | null
  size?: 'sm' | 'md' | 'lg'
  /** 'solid' = bordered chip. 'bare' = no shell, for use inside prose. */
  variant?: 'solid' | 'bare'
  /** Makes the whole chip a link. */
  to?: string | null
}>(), {
  price: null,
  priceUnit: 'cents',
  mentions: null,
  result: null,
  size: 'md',
  variant: 'solid',
  to: null
})

const cents = computed(() => {
  const p = props.price
  if (p === null || p === undefined || !Number.isFinite(p)) return null
  return Math.round(props.priceUnit === 'fraction' ? p * 100 : p)
})

const resolved = computed(() => {
  const r = (props.result || '').toLowerCase()
  return r === 'yes' ? 'yes' : r === 'no' ? 'no' : null
})

const priceClass = computed(() =>
  resolved.value === 'yes' ? 'text-success' : resolved.value === 'no' ? 'text-error' : 'text-default'
)

const text = computed(() => ({ sm: 'text-xs', md: 'text-sm', lg: 'text-base' }[props.size]))
const gap = computed(() => ({ sm: 'gap-1.5', md: 'gap-2', lg: 'gap-2.5' }[props.size]))
const pad = computed(() => ({ sm: 'px-1.5 py-0.5', md: 'px-2 py-1', lg: 'px-2.5 py-1.5' }[props.size]))

const shell = computed(() => {
  const base = ['inline-flex items-center align-middle max-w-full', text.value, gap.value]
  if (props.variant === 'solid') {
    base.push('rounded-sm border border-default bg-elevated/60', pad.value)
    if (props.to) base.push('transition-colors hover:border-accented hover:bg-accented/60')
  } else if (props.to) {
    base.push('transition-colors hover:text-highlighted')
  }
  return base
})
</script>

<template>
  <NuxtLink v-if="to" :to="to" :class="shell">
    <span class="font-mono text-highlighted truncate">
      <span aria-hidden="true" class="text-dimmed">&ldquo;</span>{{ term }}<span aria-hidden="true" class="text-dimmed">&rdquo;</span>
    </span>
    <UiTallyRail v-if="mentions" :count="mentions" :max="12" :height="10" />
    <span v-if="cents !== null" class="type-figure whitespace-nowrap" :class="priceClass">
      {{ cents }}<span class="text-dimmed">¢</span>
    </span>
  </NuxtLink>

  <span v-else :class="shell">
    <span class="font-mono text-highlighted truncate">
      <span aria-hidden="true" class="text-dimmed">&ldquo;</span>{{ term }}<span aria-hidden="true" class="text-dimmed">&rdquo;</span>
    </span>
    <UiTallyRail v-if="mentions" :count="mentions" :max="12" :height="10" />
    <span v-if="cents !== null" class="type-figure whitespace-nowrap" :class="priceClass">
      {{ cents }}<span class="text-dimmed">¢</span>
    </span>
  </span>
</template>
