<script setup lang="ts">
/**
 * UpsellBanner — the single paywall prompt for the whole site.
 *
 * Replaces the four hand-rolled yellow banners. Premium reads as INK: solid,
 * dark, confident. Amber means "a mention happened" and is never spent here.
 *
 * This component only renders the prompt — it does NOT decide whether the user
 * is gated. Keep the caller's own gate (isSubscribed, is_locked, is_premium,
 * is_limited, or field-absence) exactly as it is and wrap this in that v-if.
 */
withDefaults(defineProps<{
  /** Headline. Say what is behind the gate, not that something is locked. */
  title?: string
  /** One line on what unlocking gives them. */
  description?: string | null
  ctaLabel?: string
  ctaTo?: string
  /** Quiet secondary link, e.g. sign in for existing subscribers. */
  secondaryLabel?: string | null
  secondaryTo?: string | null
  /** 'bar' = full-width strip between sections. 'panel' = a blocking card that
   *  stands in for the hidden content itself. */
  variant?: 'bar' | 'panel'
  icon?: string
}>(), {
  title: 'Mention counts are part of the subscription',
  description: 'Subscribe to see how often each term was said, the trend across briefings, and the quoted context.',
  ctaLabel: 'See pricing',
  ctaTo: '/pricing',
  secondaryLabel: null,
  secondaryTo: null,
  variant: 'bar',
  icon: 'i-lucide-lock'
})
</script>

<template>
  <div
    class="rounded-sm bg-inverted text-inverted"
    :class="variant === 'panel' ? 'px-6 py-8 sm:px-8 sm:py-10' : 'px-5 py-4'"
  >
    <div
      class="flex gap-4"
      :class="variant === 'panel' ? 'flex-col items-start' : 'flex-col sm:flex-row sm:items-center'"
    >
      <UIcon :name="icon" class="size-5 shrink-0 opacity-70" aria-hidden="true" />

      <div class="flex-1 min-w-0">
        <p class="font-semibold" :class="variant === 'panel' ? 'type-subhead' : 'text-base'">
          {{ title }}
        </p>
        <p v-if="description" class="mt-1 text-sm opacity-70">
          {{ description }}
        </p>
        <slot />
      </div>

      <div class="flex items-center gap-3 shrink-0">
        <UButton
          :to="ctaTo"
          :label="ctaLabel"
          color="neutral"
          variant="solid"
          size="md"
          trailing-icon="i-lucide-arrow-right"
          class="bg-default text-default hover:bg-muted"
        />
        <ULink
          v-if="secondaryLabel && secondaryTo"
          :to="secondaryTo"
          class="text-sm underline underline-offset-4 opacity-70 hover:opacity-100"
        >
          {{ secondaryLabel }}
        </ULink>
      </div>
    </div>
  </div>
</template>
