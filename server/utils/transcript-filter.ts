interface TranscriptSegment {
    speaker: string
    content: string
    timestamp?: string
}

/**
 * Parse a transcript string into segments with speaker labels
 */
export function parseTranscript(transcript: string): TranscriptSegment[] {
    const segments: TranscriptSegment[] = []
    // Match speaker labels like "SPEAKER_00:", "SPEAKER_01:", "Character1:", etc.
    const speakerPattern = /^([A-Z_0-9]+|Character\d+):\s*(.*)$/gm
    const lines = transcript.split('\n')
    
    let currentSpeaker: string | null = null
    let currentContent: string[] = []
    
    for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        
        const match = trimmed.match(/^([A-Z_0-9]+|Character\d+):\s*(.*)$/)
        if (match) {
            // Save previous segment if exists
            if (currentSpeaker !== null && currentContent.length > 0) {
                segments.push({
                    speaker: currentSpeaker,
                    content: currentContent.join(' ').trim()
                })
            }
            // Start new segment
            currentSpeaker = match[1]!
            currentContent = match[2] ? [match[2]] : []
        } else if (currentSpeaker !== null) {
            // Continue current segment
            currentContent.push(trimmed)
        }
    }
    
    // Add last segment
    if (currentSpeaker !== null && currentContent.length > 0) {
        segments.push({
            speaker: currentSpeaker,
            content: currentContent.join(' ').trim()
        })
    }
    
    return segments
}

/**
 * Highlight matching text in a string
 */
function highlightText(text: string, searchString: string): string {
    if (!searchString || !searchString.trim()) {
        return escapeHtml(text)
    }
    
    const searchLower = searchString.toLowerCase()
    const textLower = text.toLowerCase()
    const parts: string[] = []
    let lastIndex = 0
    let index = textLower.indexOf(searchLower, lastIndex)
    
    // If no matches found, return escaped text
    if (index === -1) {
        return escapeHtml(text)
    }
    
    while (index !== -1) {
        // Add text before match
        if (index > lastIndex) {
            parts.push(escapeHtml(text.substring(lastIndex, index)))
        }
        // Add highlighted match
        parts.push(`<mark class="bg-yellow-200 dark:bg-yellow-900">${escapeHtml(text.substring(index, index + searchString.length))}</mark>`)
        lastIndex = index + searchString.length
        index = textLower.indexOf(searchLower, lastIndex)
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
        parts.push(escapeHtml(text.substring(lastIndex)))
    }
    
    return parts.join('')
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text: string): string {
    const div = { innerHTML: '' } as any
    div.textContent = text
    return div.innerHTML || text.replace(/[&<>"']/g, (char) => {
        const map: Record<string, string> = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        }
        return map[char] || char
    })
}

/**
 * Highlight transcript with search string and/or speaker highlighting
 * Returns highlighted transcript and match count
 */
export function highlightTranscript(
    transcript: string,
    searchString?: string,
    speakers?: string[]
): { highlightedTranscript: string; matchCount: number } {
    const segments = parseTranscript(transcript)
    
    let matchCount = 0
    const lines: string[] = []
    let currentSpeaker: string | null = null
    
    for (const segment of segments) {
        const isSpeakerMatch = speakers && speakers.length > 0 && speakers.some(speaker =>
            segment.speaker === speaker ||
            segment.speaker.toLowerCase() === speaker.toLowerCase() ||
            segment.speaker.toLowerCase().includes(speaker.toLowerCase())
        )
        
        const isContentMatch = searchString && searchString.trim() &&
            segment.content.toLowerCase().includes(searchString.toLowerCase())
        
        const isMatch = isSpeakerMatch || isContentMatch
        
        if (isMatch) {
            matchCount++
        }
        
        // Add speaker label
        if (segment.speaker !== currentSpeaker) {
            if (lines.length > 0) {
                lines.push('')
            }
            const speakerLabel = isSpeakerMatch && speakers && speakers.length > 0
                ? `<mark class="bg-blue-200 dark:bg-blue-900 font-semibold">${escapeHtml(segment.speaker)}:</mark>`
                : `${escapeHtml(segment.speaker)}:`
            lines.push(speakerLabel)
            currentSpeaker = segment.speaker
        }
        
        // Add content with highlighting
        const highlightedContent = searchString && searchString.trim()
            ? highlightText(segment.content, searchString)
            : escapeHtml(segment.content)
        
        lines.push(highlightedContent)
    }
    
    return {
        highlightedTranscript: lines.join('\n'),
        matchCount
    }
}

/**
 * Extract unique speakers from a transcript
 */
export function extractSpeakers(transcript: string): string[] {
    const segments = parseTranscript(transcript)
    const speakers = new Set<string>()
    
    for (const segment of segments) {
        speakers.add(segment.speaker)
    }
    
    return Array.from(speakers).sort()
}
