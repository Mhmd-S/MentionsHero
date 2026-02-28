<script setup lang="ts">
const { logout } = useAuth();
</script>

<template>
  <UApp>
    <div class="flex min-h-screen">
      <aside class="w-64 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 fixed top-0 left-0 h-screen overflow-y-auto">
        <div class="p-4">
          <div class="flex items-center gap-2 mb-6">
            <UIcon name="i-heroicons-chat-bubble-left-right" class="size-6 text-primary" />
            <span class="font-bold text-lg">MentionsHero</span>
            <UButton
              icon="i-heroicons-arrow-right-on-rectangle"
              variant="ghost"
              size="xs"
              color="neutral"
              class="ml-auto"
              title="Sign out"
              @click="logout"
            />
          </div>

          <nav class="space-y-1 mb-4">
            <NuxtLink
              to="/admin"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-plus-circle" class="size-5" />
              New Transcript
            </NuxtLink>
            <NuxtLink
              to="/admin/term-search"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-magnifying-glass" class="size-5" />
              Term Search
            </NuxtLink>
            <NuxtLink
              to="/admin/transcripts"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-document-text" class="size-5" />
              Transcripts
            </NuxtLink>
            <NuxtLink
              to="/admin/personas"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-user-group" class="size-5" />
              Personas
            </NuxtLink>
            <NuxtLink
              to="/admin/markets"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-chart-bar" class="size-5" />
              Markets
            </NuxtLink>
          </nav>

          <FileTree />

          <JobsSidebar />
        </div>
      </aside>

      <main class="flex-1 p-8 ml-64">
        <slot />
      </main>
    </div>
  </UApp>
</template>
