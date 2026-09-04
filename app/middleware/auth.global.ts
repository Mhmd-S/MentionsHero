/**
 * Route guard.
 *
 * The site is entirely public — every transcript, every speaker, no account, no
 * paywall. /admin is the only private zone, so this is a one-entry deny-list: an
 * unmatched URL falls through to a real 404 instead of a login wall, and a new
 * public page needs no change here.
 *
 * The session comes from @nuxtjs/supabase, hydrated from cookies during SSR, so the
 * redirect happens on the server on a hard load — no rendering a protected page and
 * bouncing a beat later.
 *
 * The module's own `global-auth` middleware is off (`supabase.redirect: false` in
 * nuxt.config.ts), so this is the only thing that redirects.
 */

/** Needs a session whose profiles.role is 'admin'. */
const ADMIN_PREFIXES = ['/admin']

function matches(path: string, prefixes: string[]): boolean {
  return prefixes.some(prefix => path === prefix || path.startsWith(`${prefix}/`))
}

export default defineNuxtRouteMiddleware(async (to) => {
  if (!matches(to.path, ADMIN_PREFIXES)) return

  const session = useSupabaseSession()

  if (!session.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }

  // The role lives in the profiles table, so it needs a backend round-trip. Client
  // only: during SSR that request would have to loop back through the /api proxy,
  // and admin pages are noindex anyway.
  if (import.meta.server) return

  const { ensureLoaded, role } = useProfile()
  await ensureLoaded()

  if (role.value !== 'admin') {
    return navigateTo('/')
  }
})
