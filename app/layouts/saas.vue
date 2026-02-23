<script setup lang="ts">
const { session, user, role, logout } = useAuth();

const isAdmin = computed(() => role.value === 'admin');

async function handleLogout() {
  await logout();
}
</script>

<template>
  <UApp>
    <div class="min-h-screen bg-white">
      <!-- Top navigation -->
      <header class="border-b border-gray-200 px-4 py-3">
        <div class="max-w-6xl mx-auto flex items-center justify-between">
          <NuxtLink to="/" class="font-bold text-lg flex items-center gap-2">
            <UIcon name="i-heroicons-microphone" class="size-5 text-primary" />
            Chanis
          </NuxtLink>

          <nav class="flex items-center gap-3">
            <NuxtLink v-if="isAdmin" to="/admin">
              <UButton variant="ghost" size="sm" icon="i-heroicons-cog-6-tooth">Admin</UButton>
            </NuxtLink>

            <template v-if="!session">
              <NuxtLink to="/login">
                <UButton variant="ghost" size="sm">Sign in</UButton>
              </NuxtLink>
              <NuxtLink to="/signup">
                <UButton size="sm">Sign up free</UButton>
              </NuxtLink>
            </template>

            <template v-else>
              <span class="text-sm text-gray-500">{{ user?.email }}</span>
              <UButton variant="ghost" size="sm" @click="handleLogout">
                Sign out
              </UButton>
            </template>
          </nav>
        </div>
      </header>

      <main>
        <slot />
      </main>
    </div>
  </UApp>
</template>
