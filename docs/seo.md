# SEO

## Overview

MentionsHero uses the `@nuxtjs/seo` umbrella module which includes robots.txt, sitemap, schema.org, and OG image generation. Additional modules: `@nuxt/image` for image optimization, `@nuxt/content` for the blog.

## Modules

| Module | Purpose |
|--------|---------|
| `@nuxtjs/seo` | Umbrella: robots, sitemap, schema-org, og-image |
| `@nuxt/image` | Image optimization (WebP, quality control) |
| `@nuxt/content` | Markdown blog system |

## Dynamic OG Images

OG images are auto-generated using `nuxt-og-image` (bundled with `@nuxtjs/seo`). Templates live in `app/components/OgImage/`:

| Template | Used By | Props |
|----------|---------|-------|
| `OgImageDefault.vue` | `/`, `/pricing`, `/markets`, `/blog`, `/transcripts/[id]`, and `/markets/[slug]` when the persona has no `image_url` | None |
| `OgImagePersona.vue` | `/personas/[slug]`, and `/markets/[slug]` when the persona has an `image_url` | `name`, `description`, `imageUrl` |
| `OgImageBlog.vue` | `/blog/[...slug]` | `title`, `description`, `date` |

`/login`, `/signup` and `/account` deliberately have no OG image — they are `noindex, nofollow`.

**The OG templates are outside the design system.** They render in Satori, not the browser, so they
carry hard-coded inline styles (currently a slate/sky palette) rather than the `ink`/`paper`/`mark`
tokens from `app/assets/css/main.css`. If they are ever restyled to match the site, the colours must
be written as literals in the template — a Satori render has no access to the CSS bundle. See
`docs/design-system.md`.

Usage in pages: `defineOgImage({ component: 'OgImagePersona', alt: '...', props: { ... } })`

**Every public page must call `defineOgImage()`** — there is no global default configured, so a
page without it emits no `og:image` at all.

`nuxt-og-image` emits the Twitter image tags for free: a `defineOgImage()` call also outputs
`twitter:card` (`summary_large_image`), `twitter:image`, `twitter:image:src`, and the
`og:image:width/height` + `twitter:image:width/height` pairs. Do **not** hand-write `twitterImage`.

Image alt text is set once, via the `alt` option on `defineOgImage()` — it produces both
`og:image:alt` and `twitter:image:alt`. Do not use `ogImageAlt` in `useSeoMeta()`; it only covers
the OG half and duplicates the tag.

Debug at: `/__og-image__/` in development.

## Canonical URLs

`nuxt-seo-utils` (bundled in `@nuxtjs/seo`) **already injects `<link rel="canonical">` on every
page**, built from `site.url` + the current route path, at `tagPriority: 'low'`. You normally do
not add one.

`canonical` is **not** a valid `useSeoMeta()` key. Passing it there silently produces a useless
`<meta name="canonical">` tag instead of a link tag. To override, use `useHead()`:

```ts
useHead({ link: [{ rel: 'canonical', href: () => `${SITE}/personas/${slug}` }] })
```

Two pages need that override, because the backend resolves a persona by slug *or* by id
(`get_persona_by_slug` falls back to an id lookup) and the frontend links with `slug || id`:

| Page | Why |
|------|-----|
| `personas/[slug].vue` | `/personas/{id}` would otherwise self-canonicalise to the id URL |
| `markets/[slug].vue` | same id fallback via `get_public_persona_markets` |

## Sitemap

Configured in `nuxt.config.ts`:
- **Dynamic**: Persona *and* markets URLs fetched from `/api/public/sitemap-urls`
- **Static**: `/`, `/pricing`, `/blog`, `/markets`
- **Auto**: Blog posts added by `@nuxt/content` integration
- **Excluded**: `/admin/**`, `/login`, `/signup`, `/account`

The `/api/public/sitemap-urls` endpoint (`backend/routers/public.py`):
- Emits `/personas/{slug or id}` and `/markets/{slug or id}`. **Most personas have no slug**, so
  the id fallback is what keeps them in the sitemap — filtering on slug alone drops nearly all of them.
- Wraps the markets half in `try/except`: the markets tables are optional for a deployment, and a
  failure there must not take the persona URLs down with it.

## Structured Data (Schema.org)

`Organization` + `WebSite` are defined once in `app/layouts/default.vue`, so every public page
inherits them. Do not redefine them per page.

| Page | Page-level Schema Types |
|------|-------------|
| Homepage | WebPage |
| Persona detail | Person (page-scoped `@id`), Breadcrumb |
| Markets listing | WebPage, Breadcrumb, FAQPage |
| Markets detail | WebPage, Breadcrumb |
| Pricing | Breadcrumb, FAQPage |
| Blog listing | Breadcrumb |
| Blog post | Article (headline, description, image, keywords, articleSection), Breadcrumb |
| Transcript detail | WebPage, Breadcrumb |
| Account | none (`noindex, nofollow`) |
| Login / Signup | none — see below |

### Gotcha: `/login` and `/signup` inherit nothing

Both pages set `definePageMeta({ layout: false })` — they render their own two-column shell (a night
`bg-ink-950` panel beside the form) rather than the public header/footer. That means they do **not**
inherit the `Organization` + `WebSite` schema defined in `app/layouts/default.vue`. This is fine:
both are `noindex, nofollow`. But do not add another page with `layout: false` and expect the site
schema to be there.

### The error page

`app/error.vue` mounts `<NuxtLayout name="default">` itself, because Nuxt renders it outside the
normal page tree. It sets `robots: 'noindex, follow'` and a status-dependent title
(`Page not found` / `Something went wrong`). Do not add `defineOgImage()` or schema to it.

### Gotcha: `definePerson` steals the site identity

`defineOrganization()` and `definePerson()` both default to the same `#identity` node id. On
persona pages an unscoped `definePerson()` therefore **evicts the site Organization** and declares
the persona to be the site's identity. `personas/[slug].vue` passes an explicit page-scoped
`'@id'` (`.../personas/{slug}#person`) to avoid this.

### Not a bug: two `Organization` nodes

`defineOrganization({ logo })` intentionally emits a second, minimal `Organization` at
`#organization` (plus an `ImageObject` at `#logo`) alongside `#identity`. This is by design in
`@unhead/schema-org` so parent nodes can reference a clean Organization. Leave it alone.

## Robots.txt

Generated by `@nuxtjs/robots`. Disallows `/admin/` and `/account`.

## Blog

Blog posts are markdown files in `content/blog/`. Collection defined in `content.config.ts`.

### Adding a new post

1. Create `content/blog/your-post-slug.md`
2. Add frontmatter:
   ```yaml
   ---
   title: "Post Title"
   description: "Short description for SEO"
   date: "YYYY-MM-DD"
   tags: ["tag1", "tag2"]
   ---
   ```
3. Write content in markdown
4. Post auto-appears on `/blog` and in sitemap

### Pages

Both follow `docs/design-system.md`.

**`app/pages/blog/index.vue`** — `UPageHeader`, then a two-tier list:

- The newest post is a **lead article**: a 12-column grid with `type-title` headline (amber
  underline on hover via `decoration-mark-500`), a `measure-wide` description, a `type-figure` date,
  reading time, tag `UBadge`s, and a 16:9 image on the right when the post has one
- Every other post is a `border-b` row whose date and reading time **hang in the left margin** at
  `lg` (a `9rem` grid column) instead of stacking under the title
- Reading time is computed by walking `@nuxt/content`'s minimark body tree (`[tag, props,
  ...children]`, leaves are strings) at 220 wpm — there is no reading-time field in the frontmatter
- Dates are authored as plain `YYYY-MM-DD` and formatted with `timeZone: 'UTC'`, so they do not
  shift a day west of UTC
- States: `UiLoadingBlock variant="rows"` → `UAlert` with retry → `UiEmptyState`

**`app/pages/blog/[...slug].vue`** — a 404 is thrown via `createError` when the path does not
resolve, so `app/error.vue` handles it.

- `UBreadcrumb`, then a grid of a `68ch` reading column plus a `14rem` margin aside holding two
  `<UiStatRow layout="stack" semantic>` rows (Published, Reading time) and the tags
- `<ContentRenderer>` inside a `.article-body measure` wrapper. **There is no `@tailwindcss/typography`
  plugin in this project** — a `prose-*` class here would do nothing. Element styling comes from
  Nuxt UI's Prose components; the page's scoped `:deep()` rules only pull heading sizes back onto
  the type scale and give `blockquote` the mark voice (`border-inline-start: 3px solid
  var(--color-mark-500)`). Scoped SFC styles are unlayered, so they win without `!important`
- A prev/next footer links the sibling posts by date order; when there is only one post it falls
  back to an "All posts" button

### RSS feed

`server/routes/rss.xml.ts` serves an RSS 2.0 feed at `/rss.xml` (newest 50 posts). It queries the
`blog` collection with the **server-side** Content v3 API (`queryCollection(event, 'blog')` from
`@nuxt/content/server` — note the `event` first argument, unlike the client composable), XML-escapes
every interpolated value, and takes its base URL from the site config.

Discovery is via a site-wide `<link rel="alternate" type="application/rss+xml">` in
`nuxt.config.ts` → `app.head.link`.

## Per-Page SEO Checklist

Every public page should have:
- `useSeoMeta()` with title, description, ogTitle, ogDescription, twitterTitle, twitterDescription
- `defineOgImage()` with the appropriate template **and an `alt`** (never omit — no global default exists)
- `useSchemaOrg()` with relevant page-level structured data + breadcrumbs
  (not Organization/WebSite — those live in the layout)
- Non-public pages (`/account`, `/transcripts/[id]`): `robots: 'noindex, nofollow'`

Do **not** add:
- `canonical` to `useSeoMeta()` — invalid key; canonical is auto-injected (see above)
- `ogImageAlt` — use `defineOgImage({ alt })` instead
- `twitterImage` — emitted automatically by `defineOgImage()`
