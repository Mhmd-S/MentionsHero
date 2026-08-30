/**
 * Auth facade over @nuxtjs/supabase.
 *
 * The module owns the client, the session and cookie-based SSR hydration; this
 * composable only adds the app-level bits on top (login/signup/logout wrappers and
 * the `profiles.role`, which is not a JWT claim). It keeps the shape the rest of
 * the app already imports — `session`, `user`, `role`, `login`, `logout`,
 * `getAccessToken` — so call sites did not have to change.
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

  /**
   * Create an account. The profile row is created by the database trigger, so
   * there is nothing to POST afterwards and nothing to lose if the tab closes.
   *
   * `emailRedirectTo` points at the /auth/confirm Nitro route, which verifies the token
   * server-side and sets the session cookie — the user lands signed in and is never
   * asked for their details a second time.
   */
  async function signup(email: string, password: string) {
    error.value = null
    actionLoading.value = true
    try {
      const { data, error: signupError } = await client.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: `${window.location.origin}/auth/confirm` },
      })

      if (signupError) {
        error.value = signupError.message
        return { ok: false as const, needsConfirmation: false }
      }

      // With email confirmation on, `session` is null and `user.identities` is an
      // empty array when the address is already registered — Supabase returns a
      // decoy user rather than leaking that the account exists. Treat both the same
      // way: tell the user to check their inbox.
      if (data.session) {
        await fetchProfile()
        return { ok: true as const, needsConfirmation: false }
      }
      return { ok: true as const, needsConfirmation: true }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sign up failed'
      return { ok: false as const, needsConfirmation: false }
    } finally {
      actionLoading.value = false
    }
  }

  async function resendConfirmation(email: string): Promise<boolean> {
    error.value = null
    const { error: resendError } = await client.auth.resend({
      type: 'signup',
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/confirm` },
    })
    if (resendError) {
      error.value = resendError.message
      return false
    }
    return true
  }

  async function sendPasswordReset(email: string): Promise<boolean> {
    error.value = null
    const { error: resetError } = await client.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/confirm?next=${encodeURIComponent('/account?recovery=1')}`,
    })
    if (resetError) {
      error.value = resetError.message
      return false
    }
    return true
  }

  /**
   * Set a new password for the signed-in user.
   *
   * This is what makes the reset link useful: /auth/confirm?type=recovery signs the
   * user in, and they then need somewhere to actually choose a new password.
   */
  async function updatePassword(password: string): Promise<boolean> {
    error.value = null
    actionLoading.value = true
    try {
      const { error: updateError } = await client.auth.updateUser({ password })
      if (updateError) {
        error.value = updateError.message
        return false
      }
      return true
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
    signup,
    logout,
    resendConfirmation,
    sendPasswordReset,
    updatePassword,
    getAccessToken,
    ensureProfileLoaded: ensureLoaded,
  }
}
