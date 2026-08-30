<script setup lang="ts">
/**
 * EmptyState — nothing here yet, and here is what to do about it.
 *
 * Replaces six drifting copies. An empty state is an invitation to act, never
 * a shrug: give `actionLabel`/`actionTo` wherever there is a sensible next move.
 * For "this URL does not resolve", use UiNotFoundState instead.
 */
withDefaults(defineProps<{
  /** Lucide name. Must exist in @iconify-json/lucide. */
  icon?: string
  /** What is empty, in plain words. */
  title: string
  /** One line on why, or what would fill it. */
  description?: string | null
  actionLabel?: string | null
  actionTo?: string | null
  actionIcon?: string | null
  /** 'card' draws a dashed container; 'plain' sits inside one you already drew. */
  variant?: 'card' | 'plain'
  size?: 'sm' | 'md'
}>(), {
  icon: 'i-lucide-inbox',
  description: null,
  actionLabel: null,
  actionTo: null,
  actionIcon: null,
  variant: 'card',
  size: 'md'
})
</script>

<template>
  <div
    class="flex flex-col items-center justify-center text-center"
    :class="[
      variant === 'card' ? 'rounded-sm border border-dashed border-default bg-muted/40' : '',
      size === 'sm' ? 'px-5 py-8 gap-3' : 'px-6 py-14 gap-4'
    ]"
  >
    <UIcon
      :name="icon"
      :class="size === 'sm' ? 'size-6' : 'size-8'"
      class="text-dimmed"
      aria-hidden="true"
    />

    <div class="max-w-md">
      <p class="font-semibold text-highlighted" :class="size === 'sm' ? 'text-base' : 'type-subhead'">
        {{ title }}
      </p>
      <p v-if="description" class="mt-2 text-sm text-muted">
        {{ description }}
      </p>
    </div>

    <slot>
      <UButton
        v-if="actionLabel && actionTo"
        :to="actionTo"
        :label="actionLabel"
        :icon="actionIcon || undefined"
        color="primary"
        variant="solid"
        size="md"
      />
    </slot>
  </div>
</template>
