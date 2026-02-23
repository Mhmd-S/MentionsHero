export const FREE_TIER_LIMIT = 5

interface ReadStatus {
  allowed: boolean
  reads_this_month: number
  limit: number
}

export function useReads() {
  const { session } = useAuth()

  async function checkAndRecordRead(transcriptId: string): Promise<ReadStatus> {
    if (!session.value) {
      return { allowed: false, reads_this_month: 0, limit: FREE_TIER_LIMIT }
    }

    try {
      return await $fetch<ReadStatus>('/api/public/reads/record', {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.value.access_token}` },
        body: { transcript_id: transcriptId },
      })
    } catch {
      // Fail open to avoid breaking UX
      return { allowed: true, reads_this_month: 0, limit: FREE_TIER_LIMIT }
    }
  }

  return { checkAndRecordRead, FREE_TIER_LIMIT }
}
