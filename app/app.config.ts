// MentionsHero — Nuxt UI runtime configuration.
//
// COLOUR
//   Nuxt UI 4 only accepts the six built-in colour slots on a component
//   `color=""` prop, because the tv() variants are generated at build time from
//   nuxt.config's `ui.theme.colors` (unset in this project => the default six).
//   The raw scales themselves live in app/assets/css/main.css.
//
//   color="primary"    -> ink    (actions, headings, PREMIUM/paywall)
//   color="secondary"  -> mark   (a mention happened; the tally; live/active)
//   color="warning"    -> mark   (same scale; use `secondary` unless the meaning
//                                 really is a warning)
//   color="success"    -> yes    (market YES, resolved-yes, upward trend ONLY)
//   color="error"      -> no     (market NO, resolved-no, downward trend ONLY)
//   color="info"       -> ink    (quiet informational surfaces)
//   neutral            -> ash
//
//   Never write a raw Tailwind palette class (text-gray-400, bg-yellow-500/5).
//   Use text-muted / text-dimmed / text-default / text-highlighted /
//   bg-default / bg-muted / bg-elevated / bg-accented / border-default, or the
//   named scales bg-mark-500, text-yes-600, border-ink-200.
//
// ICONS
//   ONE family: LUCIDE. Every name below is verified present in
//   node_modules/@iconify-json/lucide/icons.json. Pages must author
//   `i-lucide-*` only — never `i-tabler-*`, never `i-heroicons-*`.
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'ink',
      secondary: 'mark',
      success: 'yes',
      info: 'ink',
      warning: 'mark',
      error: 'no',
      neutral: 'ash'
    },
    icons: {
      arrowDown: 'i-lucide-arrow-down',
      arrowLeft: 'i-lucide-arrow-left',
      arrowRight: 'i-lucide-arrow-right',
      arrowUp: 'i-lucide-arrow-up',
      caution: 'i-lucide-circle-alert',
      check: 'i-lucide-check',
      chevronDoubleLeft: 'i-lucide-chevrons-left',
      chevronDoubleRight: 'i-lucide-chevrons-right',
      chevronDown: 'i-lucide-chevron-down',
      chevronLeft: 'i-lucide-chevron-left',
      chevronRight: 'i-lucide-chevron-right',
      chevronUp: 'i-lucide-chevron-up',
      close: 'i-lucide-x',
      copy: 'i-lucide-copy',
      copyCheck: 'i-lucide-copy-check',
      dark: 'i-lucide-moon',
      drag: 'i-lucide-grip-vertical',
      ellipsis: 'i-lucide-ellipsis',
      error: 'i-lucide-circle-x',
      external: 'i-lucide-external-link',
      eye: 'i-lucide-eye',
      eyeOff: 'i-lucide-eye-off',
      file: 'i-lucide-file-text',
      folder: 'i-lucide-folder',
      folderOpen: 'i-lucide-folder-open',
      hash: 'i-lucide-hash',
      info: 'i-lucide-info',
      light: 'i-lucide-sun',
      loading: 'i-lucide-loader-circle',
      menu: 'i-lucide-menu',
      minus: 'i-lucide-minus',
      panelClose: 'i-lucide-panel-left-close',
      panelOpen: 'i-lucide-panel-left-open',
      plus: 'i-lucide-plus',
      reload: 'i-lucide-rotate-cw',
      search: 'i-lucide-search',
      stop: 'i-lucide-square',
      success: 'i-lucide-circle-check',
      system: 'i-lucide-monitor',
      tip: 'i-lucide-lightbulb',
      upload: 'i-lucide-upload',
      warning: 'i-lucide-triangle-alert'
    }
  }
})
