/**
 * Composable for transcript analysis API interactions
 */

export interface AnalysisFolder {
  id: string;
  name: string;
  parent_id: string | null;
}

export interface TermFrequency {
  term: string;
  total_mentions: number;
  briefings_with_term: number;
  total_briefings: number;
  percentage: number;
  trend: "increasing" | "decreasing" | "stable";
  mentions_by_date: Array<{
    date: string | null;
    name: string;
    count: number;
  }>;
}

export interface TermData {
  term: string;
  count: number;
  briefings_with_term: number;
  total_briefings: number;
  percentage: number;
}

export interface NgramData {
  phrase: string;
  count: number;
  briefings_with_phrase: number;
  total_briefings: number;
  percentage: number;
}

export interface SearchMatch {
  transcript_id: string;
  transcript_name: string;
  date: string | null;
  context: string;
  position: number;
}

export interface SearchResult {
  query: string;
  total_matches: number;
  transcripts_with_matches: number;
  matches: SearchMatch[];
}

export interface SpeakerInfo {
  name: string;
  segment_count: number;
  briefings: number;
}

export function useAnalysis() {
  const { authFetch } = useAuthFetch();
  // Shared state for folder and speaker selection across all components
  // Using useState for SSR-safe shared state that persists across components
  const selectedFolderId = useState<string | null>('analysis-selected-folder', () => null);
  const folders = useState<AnalysisFolder[]>('analysis-folders', () => []);
  const selectedSpeakers = useState<string[] | null>('analysis-selected-speakers', () => null);
  const speakersList = useState<SpeakerInfo[]>('analysis-speakers-list', () => []);
  const loading = useState<boolean>('analysis-loading', () => false);
  const error = useState<string | null>('analysis-error', () => null);

  /**
   * Fetch speakers (optionally filtered by folder). Omit folderId to get all speakers.
   */
  async function getSpeakers(folderId?: string | null): Promise<SpeakerInfo[]> {
    const id = folderId ?? selectedFolderId.value;
    try {
      const result = await authFetch<{ speakers: SpeakerInfo[] }>(
        '/api/analysis/speakers',
        { query: id != null ? { folder_id: id } : {} }
      );
      speakersList.value = result.speakers || [];
      return speakersList.value;
    } catch (e: any) {
      console.error('Failed to fetch speakers:', e);
      speakersList.value = [];
      return [];
    }
  }

  /**
   * Search speakers by name (database-backed).
   */
  async function searchSpeakers(query: string, limit = 50): Promise<SpeakerInfo[]> {
    if (!query?.trim()) return [];
    try {
      const result = await authFetch<{ speakers: SpeakerInfo[] }>(
        '/api/analysis/speakers/search',
        { query: { q: query.trim(), limit } }
      );
      return result.speakers || [];
    } catch (e: any) {
      console.error('Failed to search speakers:', e);
      return [];
    }
  }

  /**
   * Fetch all folders
   */
  async function fetchFolders(): Promise<AnalysisFolder[]> {
    try {
      const result = await authFetch<AnalysisFolder[]>("/api/folders");
      folders.value = Array.isArray(result) ? result : [];
      return folders.value;
    } catch (e: any) {
      console.error("Failed to fetch folders:", e);
      return [];
    }
  }

  /**
   * Get frequency analysis for a specific term
   */
  async function getTermFrequency(
    term: string,
    caseSensitive = false,
    folderId?: string | null,
    speakers?: string | string[] | null
  ): Promise<TermFrequency | null> {
    const folder = folderId ?? selectedFolderId.value;

    loading.value = true;
    error.value = null;
    const speakerParam = speakers ?? selectedSpeakers.value;
    const speakersQuery = speakerParam
      ? Array.isArray(speakerParam)
        ? speakerParam.join(",")
        : speakerParam
      : undefined;

    try {
      const result = await authFetch<TermFrequency>(
        `/api/analysis/term/${encodeURIComponent(term)}`,
        {
          query: {
            case_sensitive: caseSensitive,
            ...(folder && { folder_id: folder }),
            ...(speakersQuery && { speakers: speakersQuery }),
          },
        }
      );
      return result;
    } catch (e: any) {
      error.value = e.message || "Failed to fetch term frequency";
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Get all terms above a frequency threshold
   */
  async function getAllTerms(
    minFrequency = 5,
    maxTerms = 500,
    folderId?: string | null,
    speakers?: string | string[] | null
  ): Promise<TermData[]> {
    const folder = folderId ?? selectedFolderId.value;

    loading.value = true;
    error.value = null;
    const speakerParam = speakers ?? selectedSpeakers.value;
    const speakersQuery = speakerParam
      ? Array.isArray(speakerParam)
        ? speakerParam.join(",")
        : speakerParam
      : undefined;

    try {
      const result = await authFetch<{ terms: TermData[] }>(
        "/api/analysis/terms",
        {
          query: {
            min_frequency: minFrequency,
            max_terms: maxTerms,
            ...(folder && { folder_id: folder }),
            ...(speakersQuery && { speakers: speakersQuery }),
          },
        }
      );
      return result.terms;
    } catch (e: any) {
      error.value = e.message || "Failed to fetch terms";
      return [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * Get n-gram phrases
   */
  async function getNgrams(
    n: 2 | 3 = 2,
    minFrequency = 3,
    maxNgrams = 200,
    folderId?: string | null,
    speakers?: string | string[] | null
  ): Promise<NgramData[]> {
    const folder = folderId ?? selectedFolderId.value;

    loading.value = true;
    error.value = null;
    const speakerParam = speakers ?? selectedSpeakers.value;
    const speakersQuery = speakerParam
      ? Array.isArray(speakerParam)
        ? speakerParam.join(",")
        : speakerParam
      : undefined;

    try {
      const result = await authFetch<{ ngrams: NgramData[] }>(
        "/api/analysis/ngrams",
        {
          query: {
            n,
            min_frequency: minFrequency,
            max_ngrams: maxNgrams,
            ...(folder && { folder_id: folder }),
            ...(speakersQuery && { speakers: speakersQuery }),
          },
        }
      );
      return result.ngrams;
    } catch (e: any) {
      error.value = e.message || "Failed to fetch ngrams";
      return [];
    } finally {
      loading.value = false;
    }
  }


  /**
   * Search for a term in context
   */
  async function searchTerm(
    query: string,
    contextChars = 200,
    folderId?: string | null,
    speakers?: string | string[] | null
  ): Promise<SearchResult | null> {
    const folder = folderId ?? selectedFolderId.value;

    loading.value = true;
    error.value = null;
    const speakerParam = speakers ?? selectedSpeakers.value;
    const speakersBody = speakerParam
      ? Array.isArray(speakerParam)
        ? speakerParam
        : [speakerParam]
      : undefined;

    try {
      const result = await authFetch<SearchResult>("/api/analysis/search", {
        method: "POST",
        body: {
          query,
          context_chars: contextChars,
          folder_id: folder,
          ...(speakersBody?.length && { speakers: speakersBody }),
        },
      });
      return result;
    } catch (e: any) {
      error.value = e.message || "Failed to search";
      return null;
    } finally {
      loading.value = false;
    }
  }


  return {
    loading: readonly(loading),
    error: readonly(error),
    folders: readonly(folders),
    selectedFolderId,
    selectedSpeakers,
    speakersList: readonly(speakersList),
    fetchFolders,
    getSpeakers,
    searchSpeakers,
    getTermFrequency,
    getAllTerms,
    getNgrams,
    searchTerm,
  };
}
