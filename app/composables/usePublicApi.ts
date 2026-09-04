/**
 * Fetch wrapper for the public API.
 *
 * The public API is fully anonymous — there is no paywall and no per-visitor
 * widening of the response — so this adds nothing to `$fetch` but a single place
 * to reach the public routes from. Kept as a seam: pages call `publicFetch`, not
 * `$fetch`, so a future base URL or header belongs here and nowhere else.
 */
export function usePublicApi() {
  async function publicFetch<T>(url: string, options?: Record<string, unknown>): Promise<T> {
    return $fetch<T>(url, options)
  }

  return { publicFetch }
}
