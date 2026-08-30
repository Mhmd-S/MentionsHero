<script setup lang="ts">
const { data: posts, status, error, refresh } = await useAsyncData('blog-list', () =>
  queryCollection('blog').order('date', 'DESC').all()
)

// Dates are authored as plain YYYY-MM-DD. Formatting them in the viewer's zone
// shifts them a day west of UTC, so pin the calendar day.
const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'long',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC'
})

function formatDate(value?: string | null): string {
  if (!value) return ''
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '' : dateFormatter.format(parsed)
}

// @nuxt/content stores the parsed body as a minimark tree: every node is
// [tag, props, ...children] and every leaf is a plain string. Walking it is the
// only way to get a word count without shipping the raw markdown.
function nodeText(node: unknown): string {
  if (typeof node === 'string') return node
  if (!Array.isArray(node)) return ''
  const [tag, , ...children] = node as unknown[]
  if (typeof tag !== 'string') return ''
  return children.map(nodeText).join(' ')
}

function readingMinutes(body: unknown): number | null {
  const nodes = (body as { value?: unknown } | undefined)?.value
  if (!Array.isArray(nodes)) return null
  const words = nodes.map(nodeText).join(' ').trim().split(/\s+/).filter(Boolean).length
  if (!words) return null
  return Math.max(1, Math.round(words / 220))
}

const items = computed(() =>
  (posts.value ?? []).map(post => ({
    path: post.path,
    title: post.title,
    description: post.description,
    tags: post.tags ?? [],
    image: post.image,
    displayDate: formatDate(post.date),
    minutes: readingMinutes(post.body)
  }))
)

const lead = computed(() => items.value[0] ?? null)
const rest = computed(() => items.value.slice(1))

useSeoMeta({
  title: 'Blog',
  description: 'Guides, analysis, and insights on press briefing transcripts, prediction markets, and public figure mentions.',
  ogTitle: 'Blog | MentionsHero',
  ogDescription: 'Guides, analysis, and insights on press briefing transcripts and prediction markets.',
  twitterCard: 'summary_large_image',
  twitterTitle: 'Blog | MentionsHero',
  twitterDescription: 'Guides, analysis, and insights on press briefing transcripts and prediction markets.',
})

defineOgImage({ component: 'OgImageDefault', alt: 'MentionsHero Blog — transcripts and prediction markets' })

useSchemaOrg([
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: 'Blog' },
    ],
  }),
])
</script>

<template>
  <div class="pb-20">
    <UPageHeader
      title="Blog"
      description="How mentions markets work, how to read a price, and what the transcripts actually show."
      :ui="{
        title: 'text-2xl sm:text-2xl text-highlighted',
        description: 'mt-4 measure text-base text-muted',
        headline: 'mb-3 type-label text-xs font-medium text-dimmed flex items-center gap-2',
      }"
    />

    <UiLoadingBlock
      v-if="status === 'pending'"
      class="mt-10"
      variant="rows"
      :count="3"
      label="Loading posts"
    />

    <UAlert
      v-else-if="error"
      class="mt-8"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      title="The post list did not load"
      description="The blog index came back empty because the request failed. Try again, or head to the transcripts in the meantime."
      :actions="[
        { label: 'Try again', color: 'neutral', variant: 'outline', icon: 'i-lucide-rotate-cw', onClick: () => refresh() },
        { label: 'Go to transcripts', color: 'neutral', variant: 'ghost', to: '/' }
      ]"
    />

    <UiEmptyState
      v-else-if="!items.length"
      class="mt-10"
      icon="i-lucide-notebook-pen"
      title="No posts published yet"
      description="When we write up how a market priced a word — and whether the transcript agreed — it lands here. The transcripts themselves are already live."
      action-label="Go to transcripts"
      action-to="/"
      action-icon="i-lucide-file-text"
    />

    <template v-else>
      <!-- Lead post: the newest one gets the full width, the image and the
           display type. Everything after it is a hanging-margin row. -->
      <article v-if="lead" class="border-b border-default py-10">
        <NuxtLink
          :to="lead.path"
          class="group grid items-start gap-8 lg:grid-cols-12 lg:gap-10"
        >
          <div :class="lead.image ? 'lg:col-span-7' : 'lg:col-span-9'">
            <p class="type-label text-dimmed">
              Latest post
            </p>

            <h2 class="type-title mt-3 text-highlighted decoration-mark-500 decoration-2 underline-offset-4 group-hover:underline">
              {{ lead.title }}
            </h2>

            <p class="measure-wide mt-4 text-muted">
              {{ lead.description }}
            </p>

            <div class="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
              <span v-if="lead.displayDate" class="type-figure text-sm text-dimmed">
                {{ lead.displayDate }}
              </span>
              <span v-if="lead.minutes" class="type-figure text-sm text-dimmed">
                {{ lead.minutes }} min read
              </span>
              <UBadge
                v-for="tag in lead.tags"
                :key="tag"
                color="neutral"
                variant="subtle"
                size="sm"
              >
                {{ tag }}
              </UBadge>
            </div>

            <span class="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
              Read the post
              <UIcon
                name="i-lucide-arrow-right"
                class="size-4 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </span>
          </div>

          <img
            v-if="lead.image"
            :src="lead.image"
            alt=""
            loading="lazy"
            decoding="async"
            class="aspect-[16/9] w-full rounded-sm border border-default object-cover lg:col-span-5"
          >
        </NuxtLink>
      </article>

      <ul v-if="rest.length" class="list-none">
        <li
          v-for="post in rest"
          :key="post.path"
          class="border-b border-default last:border-b-0"
        >
          <NuxtLink
            :to="post.path"
            class="group grid gap-x-10 gap-y-3 py-7 lg:grid-cols-[9rem_minmax(0,1fr)]"
          >
            <!-- Metadata hangs in the margin on wide screens instead of
                 stacking under the title. -->
            <div class="flex flex-row items-baseline gap-3 lg:flex-col lg:gap-1 lg:pt-1">
              <span v-if="post.displayDate" class="type-figure text-xs text-dimmed">
                {{ post.displayDate }}
              </span>
              <span v-if="post.minutes" class="type-figure text-xs text-dimmed">
                {{ post.minutes }} min read
              </span>
            </div>

            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
              <div class="min-w-0 flex-1">
                <h3 class="type-subhead text-highlighted decoration-mark-500 decoration-2 underline-offset-4 group-hover:underline">
                  {{ post.title }}
                </h3>

                <p class="measure-wide mt-2 text-muted">
                  {{ post.description }}
                </p>

                <div v-if="post.tags.length" class="mt-3 flex flex-wrap gap-1.5">
                  <UBadge
                    v-for="tag in post.tags"
                    :key="tag"
                    color="neutral"
                    variant="subtle"
                    size="sm"
                  >
                    {{ tag }}
                  </UBadge>
                </div>
              </div>

              <img
                v-if="post.image"
                :src="post.image"
                alt=""
                loading="lazy"
                decoding="async"
                class="aspect-[16/9] w-full shrink-0 rounded-sm border border-default object-cover sm:w-44"
              >
            </div>
          </NuxtLink>
        </li>
      </ul>
    </template>
  </div>
</template>
