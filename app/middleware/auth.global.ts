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

  // Login is the only public route
  if (to.path === "/login") return

  // Skip on server side
  if (import.meta.server) return

  const { session, loading } = useAuth()

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

  let currentSession = session.value

  if (!currentSession) {
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

  const { role } = useAuth()
  if (role.value !== "admin") {
    return navigateTo("/login")
  }
})
