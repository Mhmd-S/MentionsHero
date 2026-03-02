export default defineSitemapEventHandler(async () => {
  const personas = await $fetch<Array<{ slug: string; updated_at?: string }>>('http://localhost:8001/api/public/personas')

  return personas.map((p) => ({
    loc: `/personas/${p.slug}`,
    lastmod: p.updated_at,
    changefreq: 'weekly' as const,
    priority: 0.8,
  }))
})
