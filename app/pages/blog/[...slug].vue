<script setup lang="ts">
const route = useRoute()
const slugPath = '/blog/' + (Array.isArray(route.params.slug) ? route.params.slug.join('/') : route.params.slug)

const { data: postData } = await useAsyncData(`blog-${slugPath}`, () =>
  queryCollection('blog').path(slugPath).first()
)

if (!postData.value) {
  throw createError({ statusCode: 404, statusMessage: 'Post not found' })
}

// Past the guard the record is guaranteed, so the template does not need a
// v-if that can never be false.
const post = computed(() => postData.value!)

// The sibling posts, in the same order the index uses, so the footer can point
// at real neighbours instead of repeating the breadcrumb.
const { data: siblings } = await useAsyncData('blog-nav', () =>
  queryCollection('blog').order('date', 'DESC').select('title', 'path', 'date').all()
)

const position = computed(() => (siblings.value ?? []).findIndex(item => item.path === slugPath))
const newer = computed(() => (position.value > 0 ? siblings.value?.[position.value - 1] ?? null : null))
const older = computed(() => (position.value >= 0 ? siblings.value?.[position.value + 1] ?? null : null))

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
// [tag, props, ...children] and every leaf is a plain string.
function nodeText(node: unknown): string {
  if (typeof node === 'string') return node
  if (!Array.isArray(node)) return ''
  const [tag, , ...children] = node as unknown[]
  if (typeof tag !== 'string') return ''
  return children.map(nodeText).join(' ')
}

const readingMinutes = computed<number | null>(() => {
  const nodes = (post.value.body as { value?: unknown } | undefined)?.value
  if (!Array.isArray(nodes)) return null
  const words = nodes.map(nodeText).join(' ').trim().split(/\s+/).filter(Boolean).length
  if (!words) return null
  return Math.max(1, Math.round(words / 220))
})

const publishedOn = computed(() => formatDate(post.value.date))

const breadcrumbs = computed(() => [
  { label: 'Transcripts', to: '/' },
  { label: 'Blog', to: '/blog' },
  { label: post.value.title }
])

useSeoMeta({
  title: () => post.value?.title || 'Blog Post',
  description: () => post.value?.description || '',
  ogTitle: () => `${post.value?.title} | MentionsHero Blog`,
  ogDescription: () => post.value?.description || '',
  ogType: 'article',
  twitterCard: 'summary_large_image',
  articlePublishedTime: () => post.value?.date || '',
})

defineOgImage({
  component: 'OgImageBlog',
  alt: () => post.value?.title || 'MentionsHero Blog',
  props: {
    title: () => post.value?.title || '',
    description: () => post.value?.description || '',
    date: () => post.value?.date ? new Date(post.value.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '',
  },
})

useSchemaOrg([
  defineArticle({
    headline: () => post.value?.title || '',
    description: () => post.value?.description || '',
    ...(post.value?.image ? { image: post.value.image } : {}),
    datePublished: () => post.value?.date || '',
    author: {
      name: 'MentionsHero',
      url: 'https://mentionshero.com',
    },
    keywords: () => post.value?.tags || [],
    articleSection: 'Blog',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: 'Blog', item: '/blog' },
      { name: () => post.value?.title || '' },
    ],
  }),
])
</script>

<template>
  <div class="pb-20">
    <UBreadcrumb
      :items="breadcrumbs"
      class="pt-6"
      :ui="{ list: 'flex-wrap gap-y-1' }"
    />

    <!-- The reading column is a fixed 68ch measure; the metadata hangs in the
         margin beside it on wide screens instead of stacking above the text. -->
    <article class="pt-8 lg:grid lg:grid-cols-[minmax(0,68ch)_minmax(0,14rem)] lg:items-start lg:gap-x-12">
      <header class="measure-wide lg:col-start-1 lg:row-start-1">
        <h1 class="type-title text-highlighted">
          {{ post.title }}
        </h1>

        <p v-if="post.description" class="mt-4 text-lg text-toned">
          {{ post.description }}
        </p>
      </header>

      <aside class="mt-6 border-t border-default pt-4 lg:col-start-2 lg:row-start-1 lg:mt-2 lg:border-t-0 lg:pt-0">
        <dl class="flex flex-wrap gap-x-10 gap-y-3 lg:flex-col lg:gap-y-4">
          <UiStatRow
            label="Published"
            :value="publishedOn"
            layout="stack"
            size="sm"
            semantic
          />
          <UiStatRow
            v-if="readingMinutes"
            label="Reading time"
            :value="`${readingMinutes} min`"
            layout="stack"
            size="sm"
            semantic
          />
        </dl>

        <div v-if="post.tags?.length" class="mt-4 flex flex-wrap gap-1.5">
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
      </aside>

      <div class="lg:col-start-1 lg:row-start-2">
        <img
          v-if="post.image"
          :src="post.image"
          alt=""
          decoding="async"
          class="measure-wide mt-8 w-full rounded-sm border border-default object-cover"
        >

        <!-- The reading surface. Nuxt UI's Prose components do the element
             styling; these rules only pull the heading sizes back onto the type
             scale and give quotes the mark voice. There is no `prose` plugin in
             this project, so no `prose-*` class here would do anything. -->
        <div class="article-body measure mt-8">
          <ContentRenderer :value="post" />
        </div>
      </div>
    </article>

    <nav
      v-if="newer || older"
      aria-label="More posts"
      class="mt-16 border-t border-default pt-8"
    >
      <div class="grid gap-4 sm:grid-cols-2">
        <NuxtLink
          v-if="newer"
          :to="newer.path"
          class="group rounded-sm border border-default p-5 transition-colors hover:border-accented hover:bg-elevated"
        >
          <span class="type-label inline-flex items-center gap-1.5 text-dimmed">
            <UIcon name="i-lucide-arrow-left" class="size-3.5" aria-hidden="true" />
            Newer post
          </span>
          <span class="type-subhead mt-2 block text-highlighted decoration-mark-500 decoration-2 underline-offset-4 group-hover:underline">
            {{ newer.title }}
          </span>
        </NuxtLink>

        <NuxtLink
          v-if="older"
          :to="older.path"
          class="group rounded-sm border border-default p-5 transition-colors hover:border-accented hover:bg-elevated sm:text-right"
          :class="newer ? '' : 'sm:col-start-2'"
        >
          <span class="type-label inline-flex items-center gap-1.5 text-dimmed sm:flex-row-reverse">
            <UIcon name="i-lucide-arrow-right" class="size-3.5" aria-hidden="true" />
            Older post
          </span>
          <span class="type-subhead mt-2 block text-highlighted decoration-mark-500 decoration-2 underline-offset-4 group-hover:underline">
            {{ older.title }}
          </span>
        </NuxtLink>
      </div>
    </nav>

    <!-- Only when this is the only post: the breadcrumb is far above by now,
         so leave one way back. -->
    <div v-else class="mt-16 border-t border-default pt-8">
      <UButton
        to="/blog"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="All posts"
      />
    </div>
  </div>
</template>

<style scoped>
/* Scoped SFC styles are unlayered, so they outrank the Tailwind utilities the
   Prose components carry without needing !important. */
.article-body :deep(h2) {
  font-size: 1.625rem;
  line-height: 1.28;
  letter-spacing: -0.02em;
  font-weight: 600;
  margin-top: 2.75rem;
  margin-bottom: 0.875rem;
}

.article-body :deep(h3) {
  font-size: 1.25rem;
  line-height: 1.45;
  letter-spacing: -0.01em;
  font-weight: 600;
  margin-top: 2rem;
  margin-bottom: 0.5rem;
}

.article-body :deep(h4) {
  font-size: 1rem;
  line-height: 1.5;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.375rem;
}

.article-body :deep(p) {
  font-size: 1rem;
  line-height: 1.75;
  margin-top: 1.25rem;
  margin-bottom: 1.25rem;
}

.article-body :deep(li) {
  line-height: 1.75;
}

.article-body :deep(strong) {
  font-weight: 600;
  color: var(--ui-text-highlighted);
}

/* A quote is evidence, so it gets the mark. */
.article-body :deep(blockquote) {
  border-inline-start: 3px solid var(--color-mark-500);
  padding-inline-start: 1.25rem;
  font-style: normal;
  color: var(--ui-text-toned);
  margin-block: 1.75rem;
}

.article-body :deep(img) {
  border: 1px solid var(--ui-border);
  border-radius: 0.25rem;
}

/* Long tables and code blocks scroll inside themselves, never the page. */
.article-body :deep(pre),
.article-body :deep(table) {
  max-width: 100%;
}
</style>
