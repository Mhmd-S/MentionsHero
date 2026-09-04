<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { session, logout } = useAuth()
const route = useRoute()

// One name per destination. The home route is "Transcripts" in the nav, in the
// page H1 and in every breadcrumb — it is never also called "Browse" or "Home".
const navItems = computed<NavigationMenuItem[]>(() => [
  {
    label: 'Transcripts',
    icon: 'i-lucide-file-text',
    to: '/',
    active: route.path === '/'
  },
  {
    label: 'Blog',
    icon: 'i-lucide-notebook-pen',
    to: '/blog',
    active: route.path.startsWith('/blog')
  }
])

// Site-wide structured data — inherited by every page using this layout.
// Never redefine Organization or WebSite on an individual page.
useSchemaOrg([
  defineOrganization({
    name: 'MentionsHero',
    url: 'https://mentionshero.com',
    logo: 'https://mentionshero.com/favicon.svg',
    description: 'Free, searchable transcripts of press briefings, interviews and podcasts. Read what public figures actually said.',
  }),
  defineWebSite({
    name: 'MentionsHero',
    url: 'https://mentionshero.com',
    description: 'Free, searchable transcripts of press briefings, interviews and podcasts.',
  }),
])
</script>

<template>
  <div class="contents">
    <UHeader to="/">
      <template #title>
        <span class="flex items-center gap-2">
          <UiBrandMark :size="20" class="text-highlighted" />
          <span class="text-base font-bold tracking-[-0.02em] text-highlighted">MentionsHero</span>
        </span>
      </template>

      <UNavigationMenu :items="navItems" variant="pill" />

      <template #right>
        <!-- The one colour-mode toggle on the site. It is visible at every
             breakpoint, so the drawer and the footer no longer carry their own. -->
        <UColorModeButton />

        <!-- There are no visitor accounts: the whole archive is free and
             anonymous, so a signed-out header offers nothing to sign in to.
             The only session that exists is an admin's, and this strip is how
             they get back to the dashboard. Client-only, because the session is
             hydrated in the browser. -->
        <ClientOnly>
          <template v-if="session">
            <UButton
              to="/admin"
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-layout-dashboard"
              label="Admin"
              class="hidden lg:inline-flex"
            />
            <UButton
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-log-out"
              label="Sign out"
              class="hidden lg:inline-flex"
              @click="logout"
            />
          </template>
        </ClientOnly>
      </template>

      <template #body>
        <UNavigationMenu :items="navItems" orientation="vertical" class="-mx-2.5" />

        <ClientOnly>
          <template v-if="session">
            <USeparator type="dashed" class="my-4" />

            <div class="flex flex-col gap-1">
              <UButton
                to="/admin"
                variant="ghost"
                color="neutral"
                block
                class="justify-start"
                icon="i-lucide-layout-dashboard"
                label="Admin"
              />
              <UButton
                variant="ghost"
                color="neutral"
                block
                class="justify-start"
                icon="i-lucide-log-out"
                label="Sign out"
                @click="logout"
              />
            </div>
          </template>
        </ClientOnly>
      </template>
    </UHeader>

    <UMain>
      <UContainer class="px-5">
        <slot />
      </UContainer>
    </UMain>

    <!-- The footer does not repeat the nav. It says what the site holds and how
         to follow it. -->
    <UFooter>
      <template #left>
        <div class="flex flex-col gap-1.5">
          <span class="flex items-center gap-2">
            <UiBrandMark :size="16" class="text-highlighted" />
            <span class="text-sm font-bold tracking-[-0.02em] text-highlighted">MentionsHero</span>
          </span>
          <p class="max-w-xs text-sm text-muted">
            We transcribe what public figures say and make every word searchable. Free, for everyone.
          </p>
        </div>
      </template>

      <template #right>
        <div class="flex flex-col items-start gap-2 sm:items-end">
          <div class="flex items-center gap-4">
            <ULink
              to="/rss.xml"
              external
              class="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-default"
            >
              <UIcon name="i-lucide-rss" class="size-4" aria-hidden="true" />
              RSS
            </ULink>
            <span class="type-caption text-dimmed">
              &copy; {{ new Date().getFullYear() }}
            </span>
          </div>
        </div>
      </template>
    </UFooter>
  </div>
</template>
