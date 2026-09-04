/**
 * Auth facade over @nuxtjs/supabase.
 *
 * There are no user accounts on this site: the whole archive is public and
 * anonymous. Auth exists for one reason — gating /admin — so this composable is
 * down to sign in, sign out and the `profiles.role`, which is not a JWT claim.
 * Admin accounts are created in the Supabase dashboard; there is no self-signup
 * and no password-reset flow in the app.
 *
 * Note `user` is the decoded JWT payload from `auth.getClaims()`, not a Supabase
 * `User` object: the id is `user.sub`, not `user.id`.
 */
export function useAuth() {
  const client = useSupabaseClient()
  const session = useSupabaseSession()
  const user = useSupabaseUser()
  const {
    role,
    isAdmin,
    ensureLoaded,
    fetchProfile,
    clear: clearProfile,
    loading: profileLoading,
  } = useProfile()

  const actionLoading = useState<boolean>('auth-loading', () => false)
  const error = useState<string | null>('auth-error', () => null)

  // Consumers just want "is auth still settling?". app/layouts/admin.vue gates the
  // whole admin shell on this, and the role arrives with the profile, not the session.
  const loading = computed(() => actionLoading.value || profileLoading.value)

  const isLoggedIn = computed(() => !!session.value)

  async function login(email: string, password: string): Promise<boolean> {
    error.value = null
    actionLoading.value = true
    try {
      const { error: authError } = await client.auth.signInWithPassword({ email, password })
      if (authError) {
        error.value = authError.message
        return false
      }
      // Session state is set by the module's onAuthStateChange listener.
      await fetchProfile()
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sign in failed'
      return false
    } finally {
      actionLoading.value = false
    }
  }

  async function logout() {
    await client.auth.signOut()
    clearProfile()
    error.value = null
    await navigateTo('/')
  }

  function getAccessToken(): string | null {
    return session.value?.access_token ?? null
  }

  return {
    user,
    session,
    isLoggedIn,
    loading,
    error,
    role,
    isAdmin,
    login,
    logout,
    getAccessToken,
    ensureProfileLoaded: ensureLoaded,
  }
}
