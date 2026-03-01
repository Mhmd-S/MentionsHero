<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { session, logout } = useAuth()
const route = useRoute()

const navItems = computed<NavigationMenuItem[]>(() => [
  {
    label: 'Personas',
    icon: 'i-ph-users-three',
    to: '/',
    active: route.path === '/'
  },
  {
    label: 'Pricing',
    icon: 'i-ph-credit-card',
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
          <UIcon name="i-ph-chat-circle-dots-fill" class="size-5 text-primary" />
          <span class="font-semibold text-base">MentionsHero</span>
        </div>
      </template>

      <UNavigationMenu :items="navItems" variant="pill" />

      <template #right>
        <UColorModeButton />
        <template v-if="session">
          <UButton
            to="/account"
            variant="ghost"
            color="neutral"
            size="sm"
            icon="i-ph-user-circle"
            label="Account"
          />
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            icon="i-ph-sign-out"
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
      </template>

      <template #body>
        <UNavigationMenu :items="navItems" orientation="vertical" class="-mx-2.5" />

        <USeparator type="dashed" class="my-4" />

        <div class="flex flex-col gap-1">
          <template v-if="session">
            <UButton
              to="/account"
              variant="ghost"
              color="neutral"
              block
              class="justify-start"
              icon="i-ph-user-circle"
              label="Account"
            />
            <UButton
              variant="ghost"
              color="neutral"
              block
              class="justify-start"
              icon="i-ph-sign-out"
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
              icon="i-ph-sign-in"
              label="Sign In"
            />
            <UButton
              to="/signup"
              block
              class="justify-start"
              icon="i-ph-user-plus"
              label="Sign Up"
            />
          </template>
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
        <UColorModeButton />
      </template>
    </UFooter>
  </UApp>
</template>
