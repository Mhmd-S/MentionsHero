import { createClient, SupabaseClient } from '@supabase/supabase-js'

export interface StageProgress {
  current_chunk?: number
  total_chunks?: number
  substep?: string
  substep_detail?: string
}

export type JobStatus = 'pending' | 'downloading' | 'transcribing' | 'cleaning' | 'saving' | 'completed' | 'failed' | 'cancelled'

export interface Job {
  id: string
  youtube_url: string
  status: JobStatus
  stage_progress: StageProgress
  error_message: string | null
  transcript_id: string | null
  cancel_requested: boolean
  created_at: string
  updated_at: string
}

let supabaseClient: SupabaseClient | null = null

function getSupabase(): SupabaseClient {
  if (!supabaseClient) {
    const config = useRuntimeConfig()
    supabaseClient = createClient(config.supabaseUrl, config.supabaseServiceKey)
  }
  return supabaseClient
}

export async function createJob(youtubeUrl: string): Promise<Job> {
  const supabase = getSupabase()

  const { data, error } = await supabase
    .from('jobs')
    .insert({
      youtube_url: youtubeUrl,
      status: 'pending',
      stage_progress: {}
    })
    .select()
    .single()

  if (error) {
    throw createError({
      statusCode: 500,
      message: `Failed to create job: ${error.message}`
    })
  }

  return data as Job
}

export async function updateJobProgress(
  jobId: string,
  status: JobStatus,
  stageProgress?: StageProgress,
  extra?: { error_message?: string; transcript_id?: string }
): Promise<void> {
  const supabase = getSupabase()

  const updateData: Record<string, unknown> = {
    status,
    updated_at: new Date().toISOString()
  }

  if (stageProgress !== undefined) {
    updateData.stage_progress = stageProgress
  }

  if (extra?.error_message !== undefined) {
    updateData.error_message = extra.error_message
  }

  if (extra?.transcript_id !== undefined) {
    updateData.transcript_id = extra.transcript_id
  }

  const { error } = await supabase
    .from('jobs')
    .update(updateData)
    .eq('id', jobId)

  if (error) {
    console.error(`Failed to update job ${jobId}:`, error.message)
  }
}

export async function getJob(jobId: string): Promise<Job | null> {
  const supabase = getSupabase()

  const { data, error } = await supabase
    .from('jobs')
    .select()
    .eq('id', jobId)
    .single()

  if (error) {
    return null
  }

  return data as Job
}

export async function getActiveJobs(): Promise<Job[]> {
  const supabase = getSupabase()

  const { data, error } = await supabase
    .from('jobs')
    .select()
    .not('status', 'in', '("completed","failed","cancelled")')
    .order('created_at', { ascending: false })

  if (error) {
    console.error('Failed to fetch active jobs:', error.message)
    return []
  }

  return data as Job[]
}

export async function checkCancellation(jobId: string): Promise<boolean> {
  const supabase = getSupabase()

  const { data, error } = await supabase
    .from('jobs')
    .select('cancel_requested')
    .eq('id', jobId)
    .single()

  if (error) {
    console.error(`Failed to check cancellation for job ${jobId}:`, error.message)
    return false
  }

  return data?.cancel_requested === true
}

export async function markJobCancelled(jobId: string): Promise<void> {
  const supabase = getSupabase()

  const { error } = await supabase
    .from('jobs')
    .update({
      status: 'cancelled',
      updated_at: new Date().toISOString()
    })
    .eq('id', jobId)

  if (error) {
    console.error(`Failed to mark job ${jobId} as cancelled:`, error.message)
  }
}
