<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { logout } = useAuth()
const route = useRoute()

const navItems = computed<NavigationMenuItem[][]>(() => [[
  {
    label: 'New Transcript',
    icon: 'i-ph-plus-circle',
    to: '/admin',
    active: route.path === '/admin'
  },
  {
    label: 'Term Search',
    icon: 'i-ph-magnifying-glass',
    to: '/admin/term-search',
    active: route.path === '/admin/term-search'
  },
  {
    label: 'Transcripts',
    icon: 'i-ph-file-text',
    to: '/admin/transcripts',
    active: route.path.startsWith('/admin/transcripts')
  },
  {
    label: 'Personas',
    icon: 'i-ph-users-three',
    to: '/admin/personas',
    active: route.path.startsWith('/admin/personas')
  },
  {
    label: 'Markets',
    icon: 'i-ph-chart-bar',
    to: '/admin/markets',
    active: route.path.startsWith('/admin/markets')
  }
]])
</script>

<template>
  <UApp>
    <UDashboardGroup>
      <UDashboardSidebar
        collapsible
        resizable
        :min-size="15"
        :default-size="18"
        :max-size="25"
      >
        <template #header="{ collapsed }">
          <div class="flex items-center gap-2" :class="collapsed ? 'justify-center' : ''">
            <UIcon name="i-ph-chat-circle-dots-fill" class="size-5 text-primary shrink-0" />
            <span v-if="!collapsed" class="font-semibold text-sm truncate">MentionsHero</span>
          </div>
        </template>

        <template #default>
          <UNavigationMenu
            :items="navItems"
            orientation="vertical"
          />
          <div class="mt-4">
            <FileTree />
            <JobsSidebar />
          </div>
        </template>

        <template #footer="{ collapsed }">
          <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-2'">
            <UButton
              icon="i-ph-sign-out"
              variant="ghost"
              color="neutral"
              size="sm"
              :label="collapsed ? undefined : 'Sign Out'"
              :square="collapsed"
              @click="logout"
            />
            <UColorModeButton v-if="!collapsed" size="sm" />
          </div>
        </template>
      </UDashboardSidebar>

      <UDashboardPanel>
        <template #header>
          <UDashboardNavbar title="MentionsHero" icon="i-ph-chat-circle-dots-fill">
            <template #right>
              <UColorModeButton size="sm" />
            </template>
          </UDashboardNavbar>
        </template>

        <template #body>
          <slot />
        </template>
      </UDashboardPanel>
    </UDashboardGroup>
  </UApp>
</template>
