<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { logout, loading, role } = useAuth()
const route = useRoute()

const authVerified = computed(() => !loading.value && role.value === 'admin')

const navItems = computed<NavigationMenuItem[][]>(() => [[
  {
    label: 'New Transcript',
    icon: 'i-lucide-plus-circle',
    to: '/admin',
    active: route.path === '/admin'
  },
  {
    label: 'Term Search',
    icon: 'i-lucide-search',
    to: '/admin/term-search',
    active: route.path === '/admin/term-search'
  },
  {
    label: 'Transcripts',
    icon: 'i-lucide-file-text',
    to: '/admin/transcripts',
    active: route.path.startsWith('/admin/transcripts')
  },
  {
    label: 'Personas',
    icon: 'i-lucide-users',
    to: '/admin/personas',
    active: route.path.startsWith('/admin/personas')
  },
  {
    label: 'Markets',
    icon: 'i-lucide-bar-chart-2',
    to: '/admin/markets',
    active: route.path.startsWith('/admin/markets')
  },
  {
    label: 'Swing Analysis',
    icon: 'i-lucide-activity',
    to: '/admin/backtest',
    active: route.path === '/admin/backtest'
  },
  {
    label: 'AI Chat',
    icon: 'i-lucide-bot',
    to: '/admin/transcript-analysis',
    active: route.path === '/admin/transcript-analysis'
  }
]])
</script>

<template>
    <!-- Show loading while auth is being verified -->
    <div v-if="!authVerified" class="flex items-center justify-center h-screen">
      <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-primary" />
    </div>
    <UDashboardGroup v-else>
      <UDashboardSidebar
        collapsible
        resizable
        :min-size="15"
        :default-size="18"
        :max-size="25"
        :ui="{ root: 'max-h-svh' }"
      >
        <template #header="{ collapsed }">
          <div class="flex items-center gap-2" :class="collapsed ? 'justify-center' : ''">
            <UIcon name="i-lucide-message-circle" class="size-5 text-primary shrink-0" />
            <span v-if="!collapsed" class="font-semibold text-sm truncate">MentionsHero</span>
          </div>
        </template>

        <template #default>
          <UNavigationMenu
            :items="navItems"
            orientation="vertical"
            class="shrink-0"
          />
          <FileTree />
          <JobsSidebar />
        </template>

        <template #footer="{ collapsed }">
          <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-2'">
            <UButton
              icon="i-lucide-log-out"
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

      <UDashboardPanel :ui="{ root: 'max-h-svh', body: 'p-0 flex flex-col flex-1 overflow-hidden' }">
        <template #body>
          <slot />
        </template>
      </UDashboardPanel>
    </UDashboardGroup>
</template>
