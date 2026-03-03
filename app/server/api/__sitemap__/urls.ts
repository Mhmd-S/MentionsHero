export default defineSitemapEventHandler(async () => {
  const personas = await $fetch<Array<{ slug: string; updated_at?: string }>>('/api/public/personas')

  const personaUrls = personas.map((p) => ({
    loc: `/personas/${p.slug}`,
    lastmod: p.updated_at,
    changefreq: 'weekly' as const,
    priority: 0.8 as const,
  }))

  const staticPages = [
    { loc: '/pricing', changefreq: 'monthly' as const, priority: 0.6 as const },
  ]

  return [...staticPages, ...personaUrls]
})
