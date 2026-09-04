import type { Ref } from 'vue'

export interface Profile {
  first_name: string | null
  last_name: string | null
  phone: string | null
  email: string | null
  role: string | null
}

/**
 * The signed-in admin's `profiles` row, loaded from the FastAPI backend.
 *
 * The role lives in Postgres, not in the Supabase JWT, so it cannot be read from
 * `useSupabaseUser()` claims. It is fetched lazily by the /admin guard — the
 * public site is anonymous and never makes this request.
 *
 * GET /api/profile creates the row if it is somehow missing, so this call also
 * repairs accounts that predate the on_auth_user_created trigger.
 */
export function useProfile() {
  const session = useSupabaseSession()

  const profile = useState<Profile | null>('profile', () => null)
  const loading = useState<boolean>('profile-loading', () => false)
  const loadedFor = useState<string | null>('profile-loaded-for', () => null)

  const role = computed(() => profile.value?.role ?? null)
  const isAdmin = computed(() => role.value === 'admin')

  const displayName = computed(() => {
    const parts = [profile.value?.first_name, profile.value?.last_name].filter(Boolean)
    if (parts.length) return parts.join(' ')
    return profile.value?.email ?? null
  })

  function authHeaders(): Record<string, string> {
    const token = session.value?.access_token
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  async function fetchProfile(): Promise<Profile | null> {
    if (!session.value?.access_token) {
      profile.value = null
      loadedFor.value = null
      return null
    }

    loading.value = true
    try {
      profile.value = await $fetch<Profile>('/api/profile', { headers: authHeaders() })
      loadedFor.value = session.value.access_token
      return profile.value
    } catch {
      // A failed profile load must not look like "signed out" — the session is
      // still valid. Leave whatever was there and let the caller decide.
      return profile.value
    } finally {
      loading.value = false
    }
  }

  /**
   * Load the profile if it has not been loaded for the current session yet.
   * Safe to await from middleware on every navigation.
   */
  async function ensureLoaded(): Promise<Profile | null> {
    if (!session.value?.access_token) {
      profile.value = null
      loadedFor.value = null
      return null
    }
    if (profile.value && loadedFor.value) return profile.value
    if (loading.value) {
      await until(loading)
      return profile.value
    }
    return fetchProfile()
  }

  function clear() {
    profile.value = null
    loadedFor.value = null
  }

  return { profile, role, isAdmin, displayName, loading, fetchProfile, ensureLoaded, clear }
}

/** Resolve once a boolean ref goes false. */
function until(flag: Ref<boolean>): Promise<void> {
  if (!flag.value) return Promise.resolve()
  return new Promise((resolve) => {
    const stop = watch(flag, (value) => {
      if (!value) {
        stop()
        resolve()
      }
    })
  })
}
