import { defineSitemapEventHandler } from '#imports'

export default defineSitemapEventHandler(async () => {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8001'

  try {
    const personas = await $fetch<Array<{ slug: string }>>(`${backendUrl}/api/public/personas`)

    return personas.map(persona => ({
      loc: `/p/${persona.slug}`,
      changefreq: 'weekly' as const,
      priority: 0.8,
    }))
  } catch {
    return []
  }
})
