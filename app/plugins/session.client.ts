/**
 * Loads the per-user state that lives outside the Supabase session — the profile
 * (which carries `role`) and the Stripe subscription — once, whenever a session
 * appears, and clears it on sign-out.
 *
 * Doing it here rather than per page is what fixes two real bugs:
 *   * /pricing never called fetchSubscription(), so a paying subscriber landing
 *     there directly saw an enabled "Subscribe" button and could be charged twice.
 *   * the homepage upsell banner was shown to subscribers because the page had no
 *     idea whether they were subscribed.
 * Any page can now read `isSubscribed` and be right, without remembering to fetch.
 */
export default defineNuxtPlugin(() => {
  const session = useSupabaseSession()
  const { ensureLoaded: loadProfile, clear: clearProfile } = useProfile()
  const { ensureLoaded: loadSubscription, clear: clearSubscription } = useSubscription()

  watch(
    () => session.value?.access_token ?? null,
    (token, previous) => {
      if (!token) {
        clearProfile()
        clearSubscription()
        return
      }
      // A token refresh reissues the same session; nothing needs reloading.
      if (previous) return

      loadProfile()
      loadSubscription()
    },
    { immediate: true },
  )
})
