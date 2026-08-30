export function useHighlight() {
  function buildPluralPattern(term: string): string {
    const words = term.trim().split(/\s+/)

    if (words.length > 1) {
      // Compound: "Mr Speaker" / "shut down" — match spaced, hyphenated, joined forms
      const cleaned = words.map(w => w.replace(/\.+$/, ''))
      const escaped = cleaned.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      const suffix = "(?:'?s)?"
      const spaced = escaped.join('\\.?\\s+') + suffix
      const hyphenated = escaped.join('\\.?-') + suffix
      const forms = [spaced, hyphenated]
      if (words.length === 2) forms.push(escaped.join('') + suffix)
      return `\\b(${forms.join('|')})\\b`
    }

    const word = words[0] ?? term
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\\./g, '\\.?')
    const poss = "(?:'s)?"

    // Consonant+y: ally → allies
    if (/[^aeiou]y$/i.test(word)) {
      const base = escaped.slice(0, -1)
      return `\\b(${escaped}${poss}|${base}ies${poss})\\b`
    }

    // Words ending in s, sh, ch, x, z take +es plural
    const plural = /(?:s|sh|ch|x|z)$/i.test(word) ? 'es' : 's'
    return `\\b(${escaped}${poss}|${escaped}${plural}${poss})\\b`
  }

  function highlightTerm(text: string, searchTerm: string): string {
    if (!searchTerm) return text
    const regex = new RegExp(buildPluralPattern(searchTerm), 'gi')
    // Bare <mark> on purpose. The amber highlight is defined once, unlayered, in
    // app/assets/css/main.css — the accent IS the brand, so it must not be pinned
    // to a raw Tailwind yellow that drifts from the palette and breaks in dark mode.
    return text.replace(regex, '<mark>$1</mark>')
  }

  return { buildPluralPattern, highlightTerm }
}
