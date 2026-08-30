# Design System

The visual language of the public site. Read this before touching anything under `app/pages/`
(public routes), `app/layouts/default.vue`, `app/error.vue` or `app/components/ui/`.

## The idea: "the mark"

The product's atom is **a quoted word → a count → a price**. Everything in the system serves that
sentence:

- **Sans is prose. Mono is evidence.** Terms, counts, prices, timestamps, tickers and dates are
  monospace, because they are the thing being measured. Sentences are not.
- **Amber (`mark`) is the brand.** It means *a mention happened* — a highlighted term, a tally
  tick, an active state. It is never a warning, never a "premium" colour, never decoration.
- **Green (`yes`) and red (`no`) are reserved** for market outcome and trend direction only.
- **Premium reads as ink** — solid, dark, confident. `UiUpsellBanner` is `bg-inverted`, never amber.

## Where it lives

| File | What it owns |
|------|--------------|
| `app/assets/css/main.css` | Colour scales, type scale, surface tokens, the global `<mark>` rule, the custom `@utility` type classes |
| `app/app.config.ts` | Nuxt UI colour aliases and the icon map |
| `app/components/ui/*.vue` | The ten shared components (auto-imported with the `Ui` prefix) |
| `app/layouts/default.vue` | Public shell: header, nav, footer, site-wide schema.org |
| `app/error.vue` | Branded 404/500, mounts `<NuxtLayout name="default">` itself |

**Scope.** The system covers the public site. The admin area (`app/pages/admin/**` and the
non-`ui/` components: `TermSearch.vue`, `TermSection.vue`, `MarketOverviewRow.vue`,
`JobsSidebar.vue`, …) still uses raw Tailwind palette classes and has not been migrated. Do not
copy admin markup into a public page.

---

## Colour

### The scales

Declared in `app/assets/css/main.css` inside `@theme static`, each with the full 50→950 ramp:

| Scale | Role |
|-------|------|
| `ink` | Primary actions, headings, the premium/paywall voice. Near-black with a faint blue cast |
| `paper` | The light ground. Warm by a hair — `#FBFBF9`, not `#fff` |
| `night` | The dark ground — `#0B0C10`, not `neutral-900` |
| `mark` | **The** accent. `mark-500` is `#F5B301`. A mention happened |
| `yes` | Market YES, resolved-yes, rising trend. `yes-500` is `#12805C` |
| `no` | Market NO, resolved-no, falling trend. `no-500` is `#C0392B` |
| `ash` | The neutral. Warm at the top (meets paper), cool at the bottom (meets night) |

Because they live in `@theme`, every scale is also a plain Tailwind utility: `bg-mark-500`,
`text-yes-600`, `border-ink-200`, `text-paper-50`.

### Nuxt UI aliases (`app/app.config.ts`)

Nuxt UI 4 only accepts the six built-in colour slots on a component `color=""` prop — the `tv()`
variants are generated at build time from `nuxt.config`'s `ui.theme.colors`, which is unset here,
so the default six is all there is. Adding a seventh scale name to a `color=""` prop does nothing.

```
color="primary"   → ink    (actions, headings, PREMIUM/paywall)
color="secondary" → mark   (a mention happened; the tally; live/active)
color="warning"   → mark   (same scale — use `secondary` unless it really is a warning)
color="success"   → yes    (market YES / resolved-yes / rising ONLY)
color="error"     → no     (market NO / resolved-no / falling ONLY)
color="info"      → ink    (quiet informational surfaces)
neutral           → ash
```

### Surface tokens

`main.css` overrides Nuxt UI's `--ui-*` variables **unlayered**, so they outrank `@nuxt/ui`'s own
`@layer` defaults. That is what makes the light ground `paper` and the dark ground `night`.

Pages use the semantic classes, never a raw colour:

```
bg-default  bg-muted  bg-elevated  bg-accented  bg-inverted
text-dimmed  text-muted  text-toned  text-default  text-highlighted  text-inverted
border-default  border-muted  border-accented  border-inverted
```

`--ui-radius: 0.25rem` (so `rounded-sm` is the house corner) and `--ui-container: 80rem`.

### Hard rules

1. **Never write a raw Tailwind palette class** on a public page — no `text-gray-400`, no
   `bg-yellow-500/5`, no `dark:bg-slate-800`. Use a semantic class, or a named scale
   (`bg-mark-500`, `text-yes-600`, `border-ink-200`).
2. **Amber means a mention happened.** Not "warning", not "premium", not "new", not "highlight
   this CTA". If the thing being coloured is not a mention, a tally or an active/live state, it is
   not amber.
3. **Green and red are market outcome and trend.** A saved-successfully toast is not green. A
   healthy subscription is not green — `account.vue` deliberately renders an active subscription as
   `color="primary"` (ink) and reserves `color="error"` for `past_due`/`unpaid`, which the user must
   actually act on.
4. **Premium is ink.** Every paywall surface goes through `UiUpsellBanner`, which is
   `bg-inverted text-inverted`.

### The light-mode contrast guard

Nuxt UI's runtime plugin (`node_modules/@nuxt/ui/dist/runtime/plugins/colors.js`) emits
`--ui-<alias>: var(--ui-color-<alias>-500)` for `:root, :host, .light` and the **400** shade for
`.dark`. With `secondary`/`warning` aliased to `mark`, light mode would resolve them to `mark-500`
(`#F5B301`) — about 2:1 against paper as text, and ~1.9:1 under white on a solid badge. Unreadable.

So `main.css` pins them down a step, on the light ground only:

```css
:root, .light {
  --ui-secondary: #A57401;  /* mark-700 */
  --ui-warning:   #A57401;
}
```

Dark mode needs no guard: the alias already resolves to `mark-400` against `night`.

**What this means for you:**

- `text-secondary`, `<UBadge color="secondary">`, `<UButton color="secondary">` are safe in both
  themes — they are the *legible* amber, not the brand amber.
- The **true accent is untouched**. The tally, the `<mark>` wash, live states and inline figures
  use the scale directly: `bg-mark-500`, `text-mark-600 dark:text-mark-400`,
  `var(--color-mark-500)`. Pages that want brand amber as text write the explicit light/dark pair
  `text-mark-600 dark:text-mark-400` (see `markets/index.vue`, `transcripts/[id].vue`,
  `pricing.vue`) — not `text-secondary`.
- Do not "fix" a dull-looking `text-secondary` by swapping it for `text-mark-500`. That is the
  contrast bug the guard exists to prevent.

---

## Type

### The scale

Two families, self-hosted by `@nuxt/fonts` (bundled with `@nuxt/ui`):

- **Instrument Sans** — prose, headings, UI. `--font-sans`.
- **JetBrains Mono** — evidence. `--font-mono`.

There is no third family, ever. Headings are heavy Instrument Sans with tight tracking.

Seven sizes and nothing between: **12 / 14 / 16 / 20 / 26 / 34 / 48**. The Tailwind steps repeat on
purpose so a page cannot land off the scale — `text-2xl` and `text-3xl` are both 34px;
`text-4xl`, `text-5xl` and `text-6xl` are all 48px. Body is **16px, not 14px**.

Numbers use `font-variant-numeric: tabular-nums` everywhere mono is in play, so a count that
updates does not jitter.

### Type utilities

Custom Tailwind v4 `@utility` classes declared at the bottom of `main.css`. Use these instead of
inventing a size/weight pair per page.

| Utility | Renders | Use for |
|---------|---------|---------|
| `type-display` | 48 / 1.05 / -0.03em / 700 | The page-defining statement. At most one per page |
| `type-title` | 34 / 1.15 / -0.03em / 700 | Page `<h1>` or a section opener |
| `type-heading` | 26 / 1.28 / -0.02em / 600 | Section heading (`<h2>`) |
| `type-subhead` | 20 / 1.45 / -0.01em / 600 | Card title, subheading |
| `type-body` | 16 / 1.6 / 400 | Body copy |
| `type-meta` | 14 / 1.5 | Secondary prose, a caption under a heading |
| `type-caption` | 12 / 1.4 | The smallest step |
| `type-label` | 12 mono, uppercase, `0.08em` tracking, 500 | The metadata label voice. Pair with `text-dimmed` |
| `type-figure` | mono, tabular-nums, `-0.02em`, 500 | Any number that is evidence: counts, prices, percentages, tallies |
| `measure` | `max-width: 68ch` | The reading column — transcript body, blog post, long prose |
| `measure-wide` | `max-width: 76ch` | A wide heading or lead paragraph |
| `mark-hl` | The amber wash | A tracked term highlighted inside running text (see `index.vue`'s hero) |
| `rule-dotted` | `border-bottom: 1px dotted var(--ui-border-accented)` | The hairline in the transcript voice — list rows, `UiStatRow divided`, section headers |

`type-figure` sets **no font-size** — it only supplies the mono family, tabular numerals, tracking
and weight — so always pair it with a step (`type-figure text-sm`, `type-figure text-4xl`).
`type-label` does set 12px, but pages still pin it explicitly (`type-label text-xs`) inside a Nuxt UI
`:ui` slot, where a component default would otherwise survive the merge (see trap 1).

### The mono voice rule

These categories are **always** monospace — via `type-figure`, `type-label`, or a bare `font-mono`:

- mention counts, match counts, totals, page ranges (`1–20 of 340`)
- market prices and percentages (`62¢`, `48%`)
- tracked search terms and quoted words (`UiTermChip` renders the term in mono inside `“ ”`)
- dates and timestamps (`Mar 3, 2026`, `[12:04]`)
- tickers and identifiers (`KXTRUMPMENTION-26FEB22`)
- speaker names in a transcript segment (`type-label`)
- persona aliases (`font-mono text-xs`)
- metadata labels (`type-label`: MENTIONS, BRIEFINGS, TREND, PUBLISHED)
- an email address being echoed back (`signup.vue`'s confirmation step)

Prose is never mono. A button label is never mono.

### `<mark>` — the highlight

Both the backend (`backend/utils/transcript_filter.py:highlight_text`) and the frontend
(`app/composables/useHighlight.ts`, `app/components/TermSearch.vue`,
`personas/[slug].vue:highlightContext`) emit a **bare `<mark>`** with no class. The wash is defined
once, in `main.css`:

```css
mark, mark[class] {
  background-color: color-mix(in oklab, var(--color-mark-500) 32%, transparent);
  color: inherit;
  border-radius: 0.125rem;
  padding-inline: 0.15em;
  box-decoration-break: clone;
}
```

The rule is declared **unlayered** and duplicated with a `mark[class]` selector on purpose:
unlayered rules outrank everything inside `@layer`, so a `<mark>` cannot be repainted by a utility
class that rides along on it from an API response. `transcripts/[id].vue` carries the same guard a
third time in a scoped `:deep(mark)` block for the v-html reading surface.

`::selection` uses the same amber at 40%.

**Never** emit `<mark class="bg-yellow-200 …">` from anywhere — backend, composable or template.
That was the old behaviour; it drifted from the palette and rendered light-on-light in dark mode.

---

## Components

All ten live in `app/components/ui/` and auto-import with the `Ui` prefix
(`app/components/ui/TallyRail.vue` → `<UiTallyRail>`).

### `<UiBrandMark>` — the logo glyph

A scorekeeper's tally: four ticks rising off a baseline, the last struck in amber. Inline SVG,
`currentColor`, no image request.

| Prop | Type | Default |
|------|------|---------|
| `size` | `number` (px, 1:1 box) | `20` |

```vue
<UiBrandMark :size="20" class="text-highlighted" />
```

Used in the header, the footer, and the night panel on `/login` and `/signup`.

### `<UiTallyRail>` — the signature element

Amber ticks on a faint track. **Renders real data only** — when there is nothing to show it renders
nothing. Never a placeholder rail, never randomised ticks.

Two modes, picked automatically; `values` wins if both are supplied.

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `values` | `number[] \| null` | `null` | **Series mode.** One count per briefing, oldest → newest. Tick height is proportional to the peak; a zero briefing draws a baseline stub so gaps stay visible |
| `count` | `number \| null` | `null` | **Tally mode.** A single total, drawn as that many full-height ticks |
| `max` | `number` | `24` | Tally mode: most ticks before truncating (a `+` is appended) |
| `slots` | `number` | `24` | Series mode: most slots drawn; the **last** n values are kept |
| `height` | `number` | `14` | Rail height in px |
| `tickWidth` | `number` | `2` | |
| `gap` | `number` | `1` | |
| `tone` | `'mark' \| 'yes' \| 'no' \| 'neutral'` | `'mark'` | |
| `label` | `string \| null` | `null` | Accessible label; auto-written from the data when omitted |

```vue
<!-- tally: one total -->
<UiTallyRail :count="market.total_mentions" :max="12" :height="10" />

<!-- series: one tick per briefing -->
<UiTallyRail
  :values="keywordSeries"
  :slots="30"
  :label="`Mentions of ${query} per briefing, oldest first`"
/>
```

Before drawing a series rail, make sure the counts are **complete**. `personas/[slug].vue` suppresses
the rail entirely when the API's 100-match cap bites, because a rail that under-counts is worse
than no rail.

### `<UiTermChip>` — the product's visual atom

A tracked term in real typographic quotes, mono, with its market price in the same object.

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `term` | `string` | — | Required. Rendered inside `“ ”` in mono |
| `price` | `number \| null` | `null` | Omit to render the term alone |
| `priceUnit` | `'cents' \| 'fraction'` | `'cents'` | Public API prices arrive as ints 0–100. Raw Polymarket values are 0–1 → pass `fraction` |
| `mentions` | `number \| null` | `null` | Renders a small `UiTallyRail` beside the term when > 0 |
| `result` | `string \| null` | `null` | `'yes'`/`'no'` colours the price `text-success`/`text-error` |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | |
| `variant` | `'solid' \| 'bare'` | `'solid'` | `bare` drops the shell, for use inside prose |
| `to` | `string \| null` | `null` | Makes the whole chip a `NuxtLink` |

```vue
<UiTermChip :term="term.term" :price="term.price" :mentions="term.mentions" size="sm" />
<UiTermChip term="shutdown" variant="bare" size="sm" />   <!-- inline in a sentence -->
```

### `<UiStatRow>` — one label/value line in the mono voice

The label is `type-label`; the value is always `type-figure`, because a value in a StatRow is
evidence.

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `label` | `string` | — | Required. Keep it short: "Mentions", "Briefings", "Renews" |
| `value` | `string \| number \| null` | `null` | Preformat dates and prices yourself |
| `fallback` | `string` | `'—'` | Shown when the value is null/undefined/`''` |
| `tone` | `'default' \| 'mark' \| 'yes' \| 'no' \| 'muted'` | `'default'` | `yes`/`no` are market outcome or trend **only**; `mark` means a mention happened |
| `icon` | `string \| null` | `null` | Lucide name, before the label |
| `layout` | `'row' \| 'stack'` | `'row'` | `row` = label left / value right. `stack` = label above value (a KPI block) |
| `divided` | `boolean` | `false` | Draws a `rule-dotted` leader under the row |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Value size: 14 / 16 / 26 |
| `semantic` | `boolean` | `false` | Renders `<dt>`/`<dd>`. Only valid inside a `<dl>` |

The default slot replaces the value, for when it needs mixed content.

```vue
<dl class="space-y-2">
  <UiStatRow semantic label="Mentions" tone="mark" size="sm" divided>
    <span class="inline-flex items-center gap-2">
      {{ market.total_mentions }}
      <UiTallyRail :count="market.total_mentions" :max="12" :height="10" />
    </span>
  </UiStatRow>
  <UiStatRow semantic label="Trend" value="Rising" tone="yes" icon="i-lucide-trending-up" />
</dl>
```

### `<UiPersonaAvatar>` — one image/initial pair for the whole site

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `name` | `string` | — | Required. Drives the initial **and** the accessible name |
| `src` | `string \| null` | `null` | `persona.image_url`. Null/empty/failed load falls back to the initial |
| `size` | `'xs' \| 'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'` | 24 / 32 / 40 / 56 / 80 px |
| `decorative` | `boolean` | `false` | Pass `true` when a visible label already names the persona beside it |
| `active` | `boolean` | `false` | Amber ring — only to mark an active/selected persona |

```vue
<UiPersonaAvatar :name="persona.name" :src="persona.image_url" size="lg" decorative />
```

An `<img>` that 404s flips to the initial automatically, and the watcher resets that state when
`src` changes.

### `<UiFilterToggle>` — a segmented filter group

Replaces the pattern of conveying selection through button `variant` alone. It has a real
accessible contract: `role="group"`, an `aria-label`, and `aria-pressed` per option.

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `modelValue` | `string` | — | Use with `v-model` |
| `items` | `Array<{ label, value, icon?, count? }>` | — | `count` renders as a mono figure after the label |
| `label` | `string` | — | **Required.** Names the group for assistive tech: "Venue", "Status" |
| `hideLabel` | `boolean` | `false` | Keeps the label for screen readers only |
| `size` | `'xs' \| 'sm' \| 'md'` | `'sm'` | |

```vue
<UiFilterToggle v-model="sourceFilter" label="Venue" :items="sourceItems" />
```

### `<UiLoadingBlock>` — every loading state on the site

Prefer a skeleton over a spinner whenever the shape of what is coming is known. Card grids and data
rows are this app's main layout and should not flash a centred spinner.

| Prop | Type | Default | Notes |
|------|------|---------|-------|
| `variant` | `'spinner' \| 'cards' \| 'rows' \| 'text' \| 'inline'` | `'spinner'` | |
| `count` | `number` | `6` | Skeleton cards / rows / lines |
| `columns` | `2 \| 3 \| 4` | `3` | Grid columns at `lg`, `cards` variant only |
| `label` | `string` | `'Loading'` | Visible for `spinner`, `sr-only` for the rest |

| Variant | Matches |
|---------|---------|
| `cards` | A persona or market card grid |
| `rows` | A transcript or term list |
| `text` | A reading surface (transcript body, persona shell) |
| `spinner` | Short, shape-unknown waits |
| `inline` | A small spinner inside a button or a row |

```vue
<UiLoadingBlock variant="cards" :count="6" :columns="3" label="Loading speakers" />
<UiLoadingBlock variant="text" :count="8" label="Loading transcript" />
```

### `<UiEmptyState>` — nothing here yet, and what to do about it

An empty state is an invitation to act, never a shrug. Give it an action wherever there is a
sensible next move. For "this URL does not resolve", use `UiNotFoundState` instead.

| Prop | Type | Default |
|------|------|---------|
| `icon` | `string` | `'i-lucide-inbox'` |
| `title` | `string` | — (required) |
| `description` | `string \| null` | `null` |
| `actionLabel` | `string \| null` | `null` |
| `actionTo` | `string \| null` | `null` |
| `actionIcon` | `string \| null` | `null` |
| `variant` | `'card' \| 'plain'` | `'card'` (`card` draws a dashed container; `plain` sits inside one you already drew) |
| `size` | `'sm' \| 'md'` | `'md'` |

The default slot replaces the action button when you need something other than a link.

```vue
<UiEmptyState
  icon="i-lucide-search-x"
  :title="`No speaker matches “${search}”`"
  description="Try a shorter word, or clear the search to see everyone we transcribe."
>
  <UButton color="neutral" variant="outline" icon="i-lucide-x" label="Clear the search" @click="search = ''" />
</UiEmptyState>
```

### `<UiNotFoundState>` — the thing at this URL does not exist

Use inside a page whose data came back empty for a given id/slug. A real HTTP 404 is handled by
`app/error.vue`.

| Prop | Type | Default |
|------|------|---------|
| `title` | `string` | `'We could not find that page'` |
| `description` | `string \| null` | `'It may have been removed, or the address may be wrong.'` |
| `backLabel` | `string` | `'Back to transcripts'` |
| `backTo` | `string` | `'/'` |
| `icon` | `string` | `'i-lucide-search-x'` |

```vue
<UiNotFoundState
  title="That speaker is not on MentionsHero"
  description="The address may be wrong, or the speaker may have been removed."
  back-label="Back to transcripts"
  back-to="/"
/>
```

### `<UiUpsellBanner>` — the single paywall prompt

Replaces four hand-rolled yellow banners. It renders `bg-inverted text-inverted` — premium is ink.

It **only renders the prompt**. It does not decide whether the user is gated: keep the caller's own
gate (`isSubscribed`, `is_locked`, `is_premium`, `is_limited`, or field-absence) and wrap this in
that `v-if`.

| Prop | Type | Default |
|------|------|---------|
| `title` | `string` | `'Mention counts are part of the subscription'` |
| `description` | `string \| null` | `'Subscribe to see how often each term was said, the trend across briefings, and the quoted context.'` |
| `ctaLabel` | `string` | `'See pricing'` |
| `ctaTo` | `string` | `'/pricing'` |
| `secondaryLabel` | `string \| null` | `null` |
| `secondaryTo` | `string \| null` | `null` |
| `variant` | `'bar' \| 'panel'` | `'bar'` (`bar` = full-width strip between sections; `panel` = a blocking card standing in for the hidden content itself) |
| `icon` | `string` | `'i-lucide-lock'` |

Write the title as *what is behind the gate*, not *that something is locked*.

```vue
<UiUpsellBanner
  v-if="!isSubscribed"
  variant="panel"
  icon="i-lucide-text-search"
  :title="`Keyword search across ${persona.name}'s transcripts is part of the subscription`"
  description="Type any word and see every time it was said, and the sentence around it."
  :secondary-label="session ? null : 'Sign in'"
  :secondary-to="session ? null : '/login'"
/>
```

Offer the secondary "sign in" link only to a **signed-out** reader — a signed-in non-subscriber has
nothing to sign in to.

---

## Icons

**One family: Lucide.** Author `i-lucide-*` only — never `i-tabler-*`, never `i-heroicons-*`,
never `i-mdi-*`. `@iconify-json/lucide` is the only icon package installed, and
`nuxt.config.ts` sets `icon.serverBundle: 'local'` so SSR resolves them from disk instead of hitting
the Iconify API. A name from another set silently renders nothing.

`app/app.config.ts` also remaps all 42 of Nuxt UI's internal icon slots (`chevronDown`, `close`, `loading`,
`external`, …) to Lucide equivalents, so built-in component chrome matches.

### Verification one-liner

Every `i-lucide-*` name used in `app/` must exist in the installed icon set. This prints the ones
that do not (silence means all resolve):

```bash
comm -23 \
  <(grep -rhoE 'i-lucide-[a-z0-9-]+' app/ | sed 's/i-lucide-//' | sort -u) \
  <(node -p "const s=require('./node_modules/@iconify-json/lucide/icons.json');Object.keys({...s.icons,...(s.aliases||{})}).join('\n')" | sort)
```

Run it after adding icons. A typo'd name fails silently in the browser.

---

## Two traps

### 1. `UPageHeader`'s `:ui` prop merges — pin sizes with real scale utilities

Nuxt UI builds slot classes with `tv()`, which merges your `:ui` value **onto** the theme default
via `tailwind-merge`. The `PageHeader` default (`.nuxt/ui/page-header.ts`) is:

```
title:       'text-3xl sm:text-4xl text-pretty font-bold text-highlighted'
description: 'text-lg text-pretty text-muted'
```

`tailwind-merge` can only dedupe classes it recognises. `type-title` is a **custom Tailwind v4
`@utility`** — tailwind-merge has never heard of it, so it does not know it conflicts with
`text-3xl`, keeps both, and the default wins by cascade order. The heading silently renders at the
wrong size.

So on `UPageHeader`, pin sizes with **real scale utilities**, not the `type-*` classes:

```vue
<UPageHeader
  :title="persona.name"
  :ui="{
    title: 'text-2xl sm:text-2xl text-highlighted',
    description: 'mt-4 measure text-base text-muted',
    headline: 'mb-3 type-label text-xs font-medium text-dimmed flex items-center gap-2',
  }"
/>
```

`text-2xl` (34px here) dedupes `text-3xl sm:text-4xl`; `text-base` dedupes `text-lg`. `measure` and
`type-label` are safe in the same string because no default in that slot conflicts with them.

The same caution applies to any Nuxt UI `:ui` slot override. Outside `:ui` — on plain elements — the
`type-*` utilities are the right tool.

Also: `UPageHeader`'s `title` slot renders inside the `<h1>`. Put the name and nothing else there —
anything more corrupts the heading text. Avatars and badges go in `#headline` or `#links`.

### 2. Custom colour scales must live in `@theme static`

Nuxt UI's runtime colour plugin emits, at runtime:

```css
--ui-color-secondary-500: var(--color-mark-500, /* stock-Tailwind fallback */);
```

The fallback is looked up in `tailwindcss/colors`, where `mark`, `ink`, `paper`, `night`, `yes`,
`no` and `ash` do not exist — so it is the **empty string**. If Tailwind tree-shakes
`--color-mark-500` out of the bundle (which it does for any `@theme` variable it cannot see
referenced at build time), the `var()` resolves to nothing and the colour disappears at runtime,
with no build error.

`@theme static` disables that tree-shaking and emits the whole ramp unconditionally. **Do not
change `@theme static` back to `@theme`**, and declare any new scale inside the same block.

---

## Checklist for a new public page

- [ ] Semantic surface classes only — no raw Tailwind palette class
- [ ] Headings via `type-title` / `type-heading` / `type-subhead`; on `UPageHeader` use `:ui` with
      real scale utilities instead
- [ ] Every count, price, date, ticker and term in `type-figure` / `type-label` / `font-mono`
- [ ] Amber only where a mention happened; `success`/`error` only for market outcome or trend
- [ ] Long prose wrapped in `measure` (68ch) or `measure-wide` (76ch)
- [ ] Loading → `UiLoadingBlock` with the variant that matches the incoming shape
- [ ] A failed request renders a `UAlert` with a retry action, **not** an empty state
- [ ] Empty → `UiEmptyState` with a next move; bad id/slug → `UiNotFoundState`
- [ ] Paywall → `UiUpsellBanner`, wrapped in the caller's own gate
- [ ] Session-dependent UI inside `<ClientOnly>` with a fallback that reserves its space
- [ ] Icons are `i-lucide-*` and pass the verification one-liner
- [ ] `useSeoMeta()` + `defineOgImage()` + page-level `useSchemaOrg()` — see `docs/seo.md`
