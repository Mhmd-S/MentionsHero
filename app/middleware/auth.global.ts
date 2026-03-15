export default defineNuxtRouteMiddleware(async (to) => {
  // Handle Supabase auth errors in URL hash (e.g. expired OTP links)
  if (import.meta.client && to.hash) {
    const params = new URLSearchParams(to.hash.substring(1))
    const errorDescription = params.get("error_description")
    if (errorDescription) {
      return navigateTo({
        path: "/login",
        query: { error: errorDescription },
      })
    }
  }

  // Public routes - no auth needed
  const publicPaths = ["/login", "/signup", "/pricing"]
  const publicPrefixes = ["/personas", "/transcripts", "/blog", "/markets"]

  const isPublicRoute =
    to.path === "/" ||
    publicPaths.includes(to.path) ||
    publicPrefixes.some((prefix) => to.path.startsWith(prefix))

  if (isPublicRoute) return

  // Skip on server side
  if (import.meta.server) return

  const { session, loading } = useAuth()

  // Wait for the auth plugin to finish initializing
  if (loading.value) {
    await new Promise<void>((resolve) => {
      const stop = watch(loading, (val) => {
        if (!val) {
          stop()
          resolve()
        }
      })
    })
  }

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
