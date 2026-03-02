export default defineNuxtRouteMiddleware(async (to) => {
  // Public routes - no auth needed
  const publicPaths = ["/login", "/signup", "/pricing"]
  const publicPrefixes = ["/personas", "/transcripts"]

  const isPublicRoute =
    to.path === "/" ||
    publicPaths.includes(to.path) ||
    publicPrefixes.some((prefix) => to.path.startsWith(prefix))

  if (isPublicRoute) return

  // Skip on server side
  if (import.meta.server) return

  const { session, loading } = useAuth()

  // While the plugin is still initializing, don't redirect
  if (loading.value) return

  // Check for session
  let currentSession = session.value

  if (!currentSession) {
    // Fallback: check Supabase directly
    const supabase = useSupabaseClient()
    const { data } = await supabase.auth.getSession()
    if (data.session) {
      const auth = useAuth()
      await auth.init()
      currentSession = data.session
    }
  }

  if (!currentSession) {
    return navigateTo("/login")
  }

  // Admin routes require admin role (fetched from backend via useAuth)
  if (to.path.startsWith("/admin")) {
    const { role } = useAuth()
    if (role.value !== "admin") {
      return navigateTo("/")
    }
  }
})
