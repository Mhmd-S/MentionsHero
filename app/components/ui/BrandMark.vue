<script setup lang="ts">
/**
 * BrandMark — the MentionsHero glyph.
 *
 * A scorekeeper's tally: four ticks rising off a baseline, the last one struck
 * in `mark` amber because that is the mention that landed. It is the tally rail
 * compressed to a logo. Inline SVG, currentColor, no image request.
 */
withDefaults(defineProps<{
  /** Height in px. Width follows the 1:1 box. */
  size?: number
}>(), { size: 20 })
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 20 20"
    fill="none"
    class="shrink-0"
    aria-hidden="true"
    focusable="false"
  >
    <rect x="2" y="9" width="2" height="6" rx="0.5" fill="currentColor" />
    <rect x="6" y="6" width="2" height="9" rx="0.5" fill="currentColor" />
    <rect x="10" y="10" width="2" height="5" rx="0.5" fill="currentColor" />
    <rect x="14" y="3" width="2" height="12" rx="0.5" fill="var(--color-mark-500)" />
    <rect x="2" y="16.5" width="14" height="1.5" rx="0.75" fill="currentColor" opacity="0.35" />
  </svg>
</template>
