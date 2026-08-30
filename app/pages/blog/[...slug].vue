<script setup lang="ts">
const route = useRoute()
const slugPath = '/blog/' + (Array.isArray(route.params.slug) ? route.params.slug.join('/') : route.params.slug)

const { data: post } = await useAsyncData(`blog-${slugPath}`, () =>
  queryCollection('blog').path(slugPath).first()
)

if (!post.value) {
  throw createError({ statusCode: 404, statusMessage: 'Post not found' })
}

useSeoMeta({
  title: () => post.value?.title || 'Blog Post',
  description: () => post.value?.description || '',
  ogTitle: () => `${post.value?.title} | MentionsHero Blog`,
  ogDescription: () => post.value?.description || '',
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
      { name: 'Home', item: '/' },
      { name: 'Blog', item: '/blog' },
      { name: () => post.value?.title || '' },
    ],
  }),
])
</script>

<template>
  <div>
    <div v-if="post" class="max-w-3xl mx-auto py-8">
      <NuxtLink to="/blog" class="flex items-center gap-1 mb-6 text-sm text-muted hover:text-default transition-colors">
        <UIcon name="i-lucide-arrow-left" class="size-4" />
        Back to Blog
      </NuxtLink>

      <header class="mb-8">
        <div class="flex items-center gap-2 flex-wrap mb-3">
          <UBadge v-for="tag in (post.tags || [])" :key="tag" variant="subtle" size="xs">
            {{ tag }}
          </UBadge>
        </div>
        <h1 class="text-3xl font-bold mb-3">{{ post.title }}</h1>
        <p class="text-muted">
          {{ new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) }}
        </p>
      </header>

      <ContentRenderer :value="post" class="prose prose-sm dark:prose-invert max-w-none" />

      <div class="mt-12 pt-8 border-t border-muted/20">
        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
          <NuxtLink to="/blog" class="text-sm text-primary hover:underline">
            View all posts
          </NuxtLink>
          <NuxtLink to="/" class="text-sm text-primary hover:underline">
            Browse personas
          </NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>
