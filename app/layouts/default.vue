<template>
  <UApp>
    <div class="flex min-h-screen">
      <aside class="w-64 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900">
        <div class="p-4">
          <div class="flex items-center gap-2 mb-8">
            <UIcon name="i-heroicons-microphone" class="size-6 text-primary" />
            <span class="font-bold text-lg">Transcripts</span>
          </div>

          <nav class="space-y-1">
            <NuxtLink
              to="/"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-plus-circle" class="size-5" />
              New Transcript
            </NuxtLink>
            <NuxtLink
              to="/transcripts"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
              active-class="bg-primary-100 dark:bg-primary-900 text-primary"
            >
              <UIcon name="i-heroicons-document-text" class="size-5" />
              All Transcripts
            </NuxtLink>
          </nav>

          <JobsSidebar />
        </div>
      </aside>

      <main class="flex-1 p-8">
        <slot />
      </main>
    </div>
  </UApp>
</template>
