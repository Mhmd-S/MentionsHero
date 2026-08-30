<script setup lang="ts">
/**
 * TallyRail — the signature element.
 *
 * A scorekeeper's tally: amber ticks on a faint track, encoding mentions.
 * It renders REAL data only. When there is nothing to show it renders nothing —
 * never a placeholder rail, never randomised ticks.
 *
 * Two modes, picked automatically:
 *   • series mode — pass `values`: one number per briefing, oldest → newest.
 *     Tick height is proportional to that briefing's count; a zero briefing
 *     draws a baseline stub so gaps stay visible.
 *     e.g. :values="term.mentions_by_date.map(d => d.count)"
 *   • tally mode — pass `count`: a single total with no time breakdown.
 *     Draws that many full-height ticks (capped at `max`).
 *     e.g. :count="topTerm.mentions"
 *
 * `values` wins if both are supplied.
 */
const props = withDefaults(defineProps<{
  /** Per-briefing counts, oldest → newest. Series mode. */
  values?: number[] | null
  /** Total mentions with no breakdown. Tally mode. */
  count?: number | null
  /** Tally mode: most ticks drawn before truncating. */
  max?: number
  /** Series mode: most slots drawn; the LAST n values are kept. */
  slots?: number
  /** Rail height in px. */
  height?: number
  /** Tick width in px. */
  tickWidth?: number
  /** Gap between ticks in px. */
  gap?: number
  /** Which reserved colour the ticks carry. */
  tone?: 'mark' | 'yes' | 'no' | 'neutral'
  /** Accessible label. Auto-written from the data when omitted. */
  label?: string | null
}>(), {
  values: null,
  count: null,
  max: 24,
  slots: 24,
  height: 14,
  tickWidth: 2,
  gap: 1,
  tone: 'mark',
  label: null
})

const series = computed<number[]>(() => {
  const v = props.values
  if (Array.isArray(v) && v.length) {
    const clean = v.map(n => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0))
    return clean.slice(-Math.max(1, props.slots))
  }
  return []
})

const isSeries = computed(() => series.value.length > 0 && series.value.some(n => n > 0))

const total = computed(() => {
  if (isSeries.value) return series.value.reduce((a, b) => a + b, 0)
  const c = props.count
  return Number.isFinite(c as number) && (c as number) > 0 ? Math.floor(c as number) : 0
})

/** Nothing real to draw. */
const hasData = computed(() => isSeries.value || total.value > 0)

const ticks = computed<Array<{ x: number, y: number, h: number, dim: boolean }>>(() => {
  const w = props.tickWidth
  const g = props.gap
  const h = props.height

  if (isSeries.value) {
    const peak = Math.max(...series.value)
    return series.value.map((n, i) => {
      if (n <= 0) return { x: i * (w + g), y: h - 2, h: 2, dim: true }
      const scaled = Math.max(4, Math.round((n / peak) * h))
      return { x: i * (w + g), y: h - scaled, h: scaled, dim: false }
    })
  }

  const n = Math.min(total.value, props.max)
  return Array.from({ length: n }, (_, i) => ({ x: i * (w + g), y: 0, h, dim: false }))
})

const width = computed(() => {
  const n = Math.max(ticks.value.length, 1)
  return n * (props.tickWidth + props.gap) - props.gap
})

const truncated = computed(() => !isSeries.value && total.value > props.max)

const fill = computed(() => ({
  mark: 'var(--color-mark-500)',
  yes: 'var(--color-yes-500)',
  no: 'var(--color-no-500)',
  neutral: 'var(--ui-text-dimmed)'
}[props.tone]))

const a11y = computed(() => {
  if (props.label) return props.label
  const n = total.value
  const unit = n === 1 ? 'mention' : 'mentions'
  if (isSeries.value) return `${n} ${unit} across ${series.value.length} briefings`
  return `${n} ${unit}`
})
</script>

<template>
  <span
    v-if="hasData"
    class="inline-flex items-end gap-1 align-middle"
    role="img"
    :aria-label="a11y"
  >
    <svg
      :width="width"
      :height="height"
      :viewBox="`0 0 ${width} ${height}`"
      class="shrink-0 overflow-visible"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="0"
        :y="height - 1"
        :width="width"
        height="1"
        fill="currentColor"
        class="text-dimmed opacity-40"
      />
      <rect
        v-for="(t, i) in ticks"
        :key="i"
        :x="t.x"
        :y="t.y"
        :width="tickWidth"
        :height="t.h"
        :fill="t.dim ? 'currentColor' : fill"
        :class="t.dim ? 'text-dimmed opacity-50' : ''"
        rx="0.5"
      />
    </svg>
    <span v-if="truncated" class="type-caption font-mono leading-none text-dimmed" aria-hidden="true">+</span>
  </span>
</template>
