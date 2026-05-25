/**
 * Speaker analysis API helpers (used by personas page).
 */

export interface SpeakerInfo {
  name: string;
  segment_count: number;
  briefings: number;
}

export function useAnalysis() {
  const { authFetch } = useAuthFetch();
  const speakersList = useState<SpeakerInfo[]>("analysis-speakers-list", () => []);

  async function getSpeakers(folderId?: string | null): Promise<SpeakerInfo[]> {
    try {
      const result = await authFetch<{ speakers: SpeakerInfo[] }>(
        "/api/analysis/speakers",
        { query: folderId != null ? { folder_id: folderId } : {} }
      );
      speakersList.value = result.speakers || [];
      return speakersList.value;
    } catch (e: any) {
      console.error("Failed to fetch speakers:", e);
      speakersList.value = [];
      return [];
    }
  }

  async function searchSpeakers(query: string, limit = 50): Promise<SpeakerInfo[]> {
    if (!query?.trim()) return [];
    try {
      const result = await authFetch<{ speakers: SpeakerInfo[] }>(
        "/api/analysis/speakers/search",
        { query: { q: query.trim(), limit } }
      );
      return result.speakers || [];
    } catch (e: any) {
      console.error("Failed to search speakers:", e);
      return [];
    }
  }

  return {
    speakersList: readonly(speakersList),
    getSpeakers,
    searchSpeakers,
  };
}
