import { queryCollection } from '@nuxt/content/server'
import { getSiteConfig } from '#site-config/server/composables/getSiteConfig'

const MAX_ITEMS = 50

// Control characters that are not legal in XML 1.0 text.
// eslint-disable-next-line no-control-regex
const ILLEGAL_XML_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g

/** Escape text for safe inclusion in XML text nodes and attribute values. */
function escapeXml(value: unknown): string {
  return String(value ?? '')
    .replace(ILLEGAL_XML_CHARS, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

/** RFC-822 / RFC-1123 date string, or undefined when the input is unusable. */
function toRfc822(value: unknown): string | undefined {
  if (!value) return undefined
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? undefined : date.toUTCString()
}

export default defineEventHandler(async (event) => {
  const siteConfig = getSiteConfig(event)
  const siteUrl = (siteConfig.url || 'https://mentionshero.com').replace(/\/+$/, '')
  const siteName = siteConfig.name || 'MentionsHero'

  const posts = await queryCollection(event, 'blog')
    .select('path', 'title', 'description', 'date', 'tags')
    .order('date', 'DESC')
    .limit(MAX_ITEMS)
    .all()

  const feedUrl = `${siteUrl}/rss.xml`
  const blogUrl = `${siteUrl}/blog`
  const feedTitle = `${siteName} Blog`
  const feedDescription
    = 'Guides, analysis, and insights on press briefing transcripts, prediction markets, and public figure mentions.'

  const lastBuildDate = toRfc822(posts[0]?.date) ?? new Date().toUTCString()

  const items = posts.map((post) => {
    const path = String(post.path || '')
    const link = `${siteUrl}${path.startsWith('/') ? path : `/${path}`}`
    const pubDate = toRfc822(post.date)
    const categories = Array.isArray(post.tags) ? post.tags : []

    return [
      '    <item>',
      `      <title>${escapeXml(post.title)}</title>`,
      `      <link>${escapeXml(link)}</link>`,
      `      <guid isPermaLink="true">${escapeXml(link)}</guid>`,
      `      <description>${escapeXml(post.description)}</description>`,
      ...(pubDate ? [`      <pubDate>${escapeXml(pubDate)}</pubDate>`] : []),
      ...categories.map(tag => `      <category>${escapeXml(tag)}</category>`),
      '    </item>',
    ].join('\n')
  })

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '  <channel>',
    `    <title>${escapeXml(feedTitle)}</title>`,
    `    <link>${escapeXml(blogUrl)}</link>`,
    `    <description>${escapeXml(feedDescription)}</description>`,
    '    <language>en</language>',
    `    <lastBuildDate>${escapeXml(lastBuildDate)}</lastBuildDate>`,
    `    <atom:link href="${escapeXml(feedUrl)}" rel="self" type="application/rss+xml" />`,
    ...items,
    '  </channel>',
    '</rss>',
    '',
  ].join('\n')

  setHeader(event, 'content-type', 'application/rss+xml; charset=utf-8')
  setHeader(event, 'cache-control', 'public, max-age=600, s-maxage=600')

  return xml
})
