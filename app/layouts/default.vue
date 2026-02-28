<script setup lang="ts">
const { session, logout } = useAuth()
</script>

<template>
  <UApp>
    <div class="min-h-screen flex flex-col">
      <!-- Top Navigation -->
      <header class="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex items-center justify-between h-16">
            <!-- Logo -->
            <NuxtLink to="/" class="flex items-center gap-2">
              <UIcon name="i-heroicons-chat-bubble-left-right" class="size-6 text-primary" />
              <span class="font-bold text-lg">MentionsHero</span>
            </NuxtLink>

            <!-- Navigation -->
            <nav class="flex items-center gap-6">
              <NuxtLink
                to="/"
                class="text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                active-class="text-primary"
              >
                Personas
              </NuxtLink>
              <NuxtLink
                to="/pricing"
                class="text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                active-class="text-primary"
              >
                Pricing
              </NuxtLink>
            </nav>

            <!-- Auth -->
            <div class="flex items-center gap-3">
              <template v-if="session">
                <NuxtLink to="/account">
                  <UButton variant="ghost" size="sm" icon="i-heroicons-user-circle">
                    Account
                  </UButton>
                </NuxtLink>
                <UButton
                  variant="ghost"
                  size="sm"
                  color="neutral"
                  icon="i-heroicons-arrow-right-on-rectangle"
                  @click="logout"
                >
                  Sign Out
                </UButton>
              </template>
              <template v-else>
                <NuxtLink to="/login">
                  <UButton variant="ghost" size="sm">Sign In</UButton>
                </NuxtLink>
                <NuxtLink to="/signup">
                  <UButton size="sm">Sign Up</UButton>
                </NuxtLink>
              </template>
            </div>
          </div>
        </div>
      </header>

      <!-- Main Content -->
      <main class="flex-1">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <slot />
        </div>
      </main>
    </div>
  </UApp>
</template>
