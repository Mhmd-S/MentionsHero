<script setup lang="ts">
/**
 * LoadingBlock — every loading state on the site.
 *
 * Replaces eight hand-rolled spinners. Prefer a skeleton over a spinner whenever
 * you know the shape of what is coming: card grids and data rows are this app's
 * main layout and should not flash a centred spinner.
 *
 * Variants
 *   'spinner'  centred spinner + label. Use for short, shape-unknown waits.
 *   'cards'    a grid of card skeletons. Matches a persona/market card grid.
 *   'rows'     stacked row skeletons. Matches a transcript or term list.
 *   'text'     stacked prose lines. Matches a reading surface.
 *   'inline'   a small spinner sized to sit inside a button or a row.
 */
withDefaults(defineProps<{
  variant?: 'spinner' | 'cards' | 'rows' | 'text' | 'inline'
  /** How many skeleton cards / rows / lines to draw. */
  count?: number
  /** Grid columns at lg for the 'cards' variant. */
  columns?: 2 | 3 | 4
  /** Visible text for 'spinner'; screen-reader text for every other variant. */
  label?: string
}>(), {
  variant: 'spinner',
  count: 6,
  columns: 3,
  label: 'Loading'
})
</script>

<template>
  <div role="status" :aria-label="label">
    <!-- spinner -->
    <div v-if="variant === 'spinner'" class="flex flex-col items-center justify-center gap-3 py-16">
      <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-dimmed" aria-hidden="true" />
      <span class="type-label text-dimmed">{{ label }}</span>
    </div>

    <!-- inline -->
    <UIcon
      v-else-if="variant === 'inline'"
      name="i-lucide-loader-circle"
      class="size-4 animate-spin text-dimmed"
      aria-hidden="true"
    />

    <!-- cards -->
    <div
      v-else-if="variant === 'cards'"
      class="grid gap-4 sm:grid-cols-2"
      :class="{ 'lg:grid-cols-2': columns === 2, 'lg:grid-cols-3': columns === 3, 'lg:grid-cols-4': columns === 4 }"
    >
      <div
        v-for="i in count"
        :key="i"
        class="rounded-sm border border-default bg-elevated/40 p-4"
        aria-hidden="true"
      >
        <div class="flex items-center gap-3">
          <USkeleton class="size-10 rounded-full" />
          <div class="flex-1 space-y-2">
            <USkeleton class="h-4 w-2/3" />
            <USkeleton class="h-3 w-1/3" />
          </div>
        </div>
        <USkeleton class="mt-4 h-3 w-full" />
        <USkeleton class="mt-2 h-3 w-4/5" />
        <USkeleton class="mt-4 h-3.5 w-20" />
      </div>
    </div>

    <!-- rows -->
    <div v-else-if="variant === 'rows'" class="divide-y divide-default border-y border-default" aria-hidden="true">
      <div v-for="i in count" :key="i" class="flex items-center gap-4 py-3.5">
        <USkeleton class="h-4 flex-1" />
        <USkeleton class="hidden h-3 w-24 sm:block" />
        <USkeleton class="h-3.5 w-14" />
      </div>
    </div>

    <!-- text -->
    <div v-else class="measure space-y-3" aria-hidden="true">
      <USkeleton v-for="i in count" :key="i" class="h-4" :class="i % 4 === 0 ? 'w-3/5' : 'w-full'" />
    </div>

    <span v-if="variant !== 'spinner'" class="sr-only">{{ label }}</span>
  </div>
</template>
