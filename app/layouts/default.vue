<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { session, logout } = useAuth()
const route = useRoute()

const navItems = computed<NavigationMenuItem[]>(() => [
  {
    label: 'Personas',
    icon: 'i-lucide-users',
    to: '/',
    active: route.path === '/'
  },
  {
    label: 'Pricing',
    icon: 'i-lucide-credit-card',
    to: '/pricing',
    active: route.path === '/pricing'
  }
])
</script>

<template>
  <UApp>
    <UHeader :to="'/'">
      <template #title>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-message-circle" class="size-5 text-primary" />
          <span class="font-semibold text-base">MentionsHero</span>
        </div>
      </template>

      <UNavigationMenu :items="navItems" variant="pill" />

      <template #right>
        <UColorModeButton class="hidden lg:inline-flex" />
        <ClientOnly>
          <template v-if="session">
            <UButton
              to="/account"
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-circle-user"
              label="Account"
            />
            <UButton
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-log-out"
              label="Sign Out"
              @click="logout"
            />
          </template>
          <template v-else>
            <UButton
              to="/login"
              variant="ghost"
              color="neutral"
              size="sm"
              label="Sign In"
            />
            <UButton
              to="/signup"
              size="sm"
              label="Sign Up"
            />
          </template>
        </ClientOnly>
      </template>

      <template #body>
        <UNavigationMenu :items="navItems" orientation="vertical" class="-mx-2.5" />

        <USeparator type="dashed" class="my-4" />

        <div class="flex flex-col gap-1">
          <ClientOnly>
            <template v-if="session">
              <UButton
                to="/account"
                variant="ghost"
                color="neutral"
                block
                class="justify-start"
                icon="i-lucide-circle-user"
                label="Account"
              />
              <UButton
                variant="ghost"
                color="neutral"
                block
                class="justify-start"
                icon="i-lucide-log-out"
                label="Sign Out"
                @click="logout"
              />
            </template>
            <template v-else>
              <UButton
                to="/login"
                variant="ghost"
                color="neutral"
                block
                class="justify-start"
                icon="i-lucide-log-in"
                label="Sign In"
              />
              <UButton
                to="/signup"
                block
                class="justify-start"
                icon="i-lucide-user-plus"
                label="Sign Up"
              />
            </template>
          </ClientOnly>
        </div>

        <USeparator type="dashed" class="my-4" />

        <div class="flex items-center justify-between">
          <span class="text-sm text-muted">Theme</span>
          <UColorModeButton />
        </div>
      </template>
    </UHeader>

    <UMain>
      <UContainer>
        <slot />
      </UContainer>
    </UMain>

    <UFooter>
      <template #left>
        <span class="text-sm text-muted">
          &copy; {{ new Date().getFullYear() }} MentionsHero
        </span>
      </template>

      <template #right>
        <UColorModeButton v-if="!$device.isMobile" />
      </template>
    </UFooter>
  </UApp>
</template>
