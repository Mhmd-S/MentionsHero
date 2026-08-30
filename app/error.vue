<script setup lang="ts">
import type { NuxtError } from '#app'

/**
 * Branded error page. Nuxt renders this outside the normal page tree, so it
 * mounts the default layout itself — otherwise a 404 drops the visitor onto an
 * unbranded stock page with no way back.
 */
const props = defineProps<{ error: NuxtError }>()

const status = computed(() => Number(props.error?.statusCode) || 500)
const isNotFound = computed(() => status.value === 404)

const heading = computed(() =>
  isNotFound.value ? 'Nothing is filed at this address' : 'The site could not load that page'
)

const explanation = computed(() =>
  isNotFound.value
    ? 'The transcript, persona or market you asked for is not here. It may have been removed, or the address may be mistyped.'
    : 'Something on our side failed while building this page. The transcripts and market data are unaffected — try again, and it will usually come back.'
)

// The raw message is useful on a 500 and noise on a 404.
const detail = computed(() => {
  if (isNotFound.value) return null
  const m = props.error?.message?.trim()
  return m && m.length < 300 ? m : null
})

function goHome() {
  clearError({ redirect: '/' })
}

function retry() {
  clearError({ redirect: useRoute().fullPath })
}

useSeoMeta({
  title: isNotFound.value ? 'Page not found' : 'Something went wrong',
  robots: 'noindex, follow'
})
</script>

<template>
  <NuxtLayout name="default">
    <div class="flex min-h-[60vh] flex-col justify-center py-16">
      <div class="measure">
        <p class="type-label text-dimmed">
          Error {{ status }}
        </p>

        <h1 class="mt-3 type-title text-highlighted">
          {{ heading }}
        </h1>

        <p class="mt-4 text-base text-muted">
          {{ explanation }}
        </p>

        <p
          v-if="detail"
          class="mt-4 overflow-x-auto rounded-sm border border-default bg-muted px-3 py-2 font-mono text-sm text-toned"
        >{{ detail }}</p>

        <div class="mt-8 flex flex-wrap items-center gap-3">
          <UButton
            label="Go to transcripts"
            icon="i-lucide-arrow-left"
            color="primary"
            variant="solid"
            size="md"
            @click="goHome"
          />
          <UButton
            v-if="!isNotFound"
            label="Try this page again"
            icon="i-lucide-rotate-cw"
            color="neutral"
            variant="outline"
            size="md"
            @click="retry"
          />
          <UButton
            v-else
            to="/markets"
            label="Browse markets"
            color="neutral"
            variant="outline"
            size="md"
            trailing-icon="i-lucide-arrow-right"
          />
        </div>
      </div>
    </div>
  </NuxtLayout>
</template>
