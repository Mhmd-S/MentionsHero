export default defineNuxtRouteMiddleware((to) => {
  // Skip auth check for login page
  if (to.path === "/login") return;

  const { session, loading } = useAuth();

  // While the plugin is still initializing, don't redirect (client-side only)
  if (import.meta.server) return;
  if (loading.value) return;

  if (!session.value) {
    return navigateTo("/login");
  }
});
