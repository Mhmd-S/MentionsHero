/**
 * Route guard.
 *
 * This is a deny-list, deliberately. Almost every route on this site is public, so
 * naming the two private zones is both shorter and safer than allow-listing the
 * public ones: a new public page needs no change here, and — the reason it was
 * rewritten — an unmatched URL now falls through to a real 404 instead of being
 * redirected to /login. An allow-list turned every typo into a soft 404 sitting
 * behind a login wall, which is bad for visitors and worse for search.
 *
 * The session comes from @nuxtjs/supabase, hydrated from cookies during SSR, so the
 * redirect happens on the server on a hard load — no rendering a protected page and
 * bouncing a beat later.
 *
 * The module's own `global-auth` middleware is off (`supabase.redirect: false` in
 * nuxt.config.ts), so this is the only thing that redirects.
 */

/** Needs any session. */
const USER_PREFIXES = ['/account']

/** Needs a session whose profiles.role is 'admin'. */
const ADMIN_PREFIXES = ['/admin']

function matches(path: string, prefixes: string[]): boolean {
  return prefixes.some(prefix => path === prefix || path.startsWith(`${prefix}/`))
}

export default defineNuxtRouteMiddleware(async (to) => {
  // Supabase reports failed email links in the URL fragment, which never reaches the
  // server. Surface it on /login instead of dropping the user on a page that looks
  // like nothing happened.
  if (import.meta.client && to.hash && to.path !== '/login') {
    const description = new URLSearchParams(to.hash.slice(1)).get('error_description')
    if (description) {
      return navigateTo({ path: '/login', query: { error: description } })
    }
  }

  const needsAdmin = matches(to.path, ADMIN_PREFIXES)
  if (!needsAdmin && !matches(to.path, USER_PREFIXES)) return

  const session = useSupabaseSession()

  if (!session.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }

  if (!needsAdmin) return

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
