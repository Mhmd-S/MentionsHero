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
    label: 'Markets',
    icon: 'i-lucide-chart-bar',
    to: '/markets',
    active: route.path.startsWith('/markets')
  },
  {
    label: 'Pricing',
    icon: 'i-lucide-credit-card',
    to: '/pricing',
    active: route.path === '/pricing'
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
    description: 'Search and analyze press briefing transcripts. Track what public figures say, linked to Kalshi mentions prediction markets.',
  }),
  defineWebSite({
    name: 'MentionsHero',
    url: 'https://mentionshero.com',
    description: 'Search and analyze press briefing transcripts linked to Kalshi mentions prediction markets.',
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

        <!-- The auth cluster depends on the client session, so it must be
             client-only. The fallback reserves the exact strip it will occupy,
             otherwise the header's right edge jumps on every page load. -->
        <ClientOnly>
          <template #fallback>
            <div class="hidden h-8 w-[184px] lg:block" aria-hidden="true" />
          </template>

          <template v-if="session">
            <UButton
              to="/account"
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-circle-user"
              label="Account"
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
          <template v-else>
            <UButton
              to="/login"
              variant="ghost"
              color="neutral"
              size="sm"
              label="Sign in"
              class="hidden lg:inline-flex"
            />
            <UButton
              to="/signup"
              size="sm"
              label="Start tracking"
              class="hidden lg:inline-flex"
            />
          </template>
        </ClientOnly>
      </template>

      <template #body>
        <UNavigationMenu :items="navItems" orientation="vertical" class="-mx-2.5" />

        <USeparator type="dashed" class="my-4" />

        <div class="flex flex-col gap-1">
          <ClientOnly>
            <template #fallback>
              <div class="h-20" aria-hidden="true" />
            </template>

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
                label="Sign out"
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
                label="Sign in"
              />
              <UButton
                to="/signup"
                block
                class="justify-start"
                icon="i-lucide-user-plus"
                label="Start tracking"
              />
            </template>
          </ClientOnly>
        </div>
      </template>
    </UHeader>

    <UMain>
      <UContainer class="px-5">
        <slot />
      </UContainer>
    </UMain>

    <!-- The footer does not repeat the nav. It says what the site counts, where
         the numbers come from, and how to subscribe to them. -->
    <UFooter>
      <template #left>
        <div class="flex flex-col gap-1.5">
          <span class="flex items-center gap-2">
            <UiBrandMark :size="16" class="text-highlighted" />
            <span class="text-sm font-bold tracking-[-0.02em] text-highlighted">MentionsHero</span>
          </span>
          <p class="max-w-xs text-sm text-muted">
            We transcribe what public figures say, count the words that markets price, and show both side by side.
          </p>
        </div>
      </template>

      <template #right>
        <div class="flex flex-col items-start gap-2 sm:items-end">
          <p class="type-label text-dimmed">
            Market data — Kalshi &amp; Polymarket
          </p>
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
