/**
 * Composable for ML training API interactions
 */

export interface TrainingJob {
  id: string;
  persona_id: string;
  status: string;
  stage_progress: Record<string, any>;
  error_message: string | null;
  total_segments: number;
  train_segments: number;
  valid_segments: number;
  test_segments: number;
  config: Record<string, any>;
  adapter_path: string | null;
  data_path: string | null;
  final_train_loss: number | null;
  final_valid_loss: number | null;
  training_duration_seconds: number | null;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  cancel_requested: boolean;
}

export interface InferenceResult {
  personaId: string;
  prompt: string;
  completion: string;
  tokensGenerated: number;
}

export interface AvailableModel {
  id: string;
  label: string;
  params: string;
  ram: string;
}

export interface TrainingConfig {
  model?: string;
  iterations?: number;
  learningRate?: number;
  batchSize?: number;
  maxSeqLength?: number;
  gradAccumulationSteps?: number;
  loraRank?: number;
  loraLayers?: number;
  loraDropout?: number;
  loraScale?: number;
  minWordCount?: number;
  maxTokens?: number;
}

export function useMLTraining() {
  const { authFetch } = useAuthFetch();

  async function startTraining(
    personaId: string,
    folderId?: string,
    config?: TrainingConfig
  ): Promise<{ jobId: string; status: string } | null> {
    try {
      return await authFetch('/api/ml-training/train', {
        method: 'POST',
        body: { personaId, folderId, ...config },
      });
    } catch (e: any) {
      console.error('Failed to start training:', e);
      return null;
    }
  }

  async function getTrainingJob(jobId: string): Promise<TrainingJob | null> {
    try {
      return await authFetch<TrainingJob>(`/api/ml-training/jobs/${jobId}`);
    } catch (e: any) {
      console.error('Failed to fetch training job:', e);
      return null;
    }
  }

  async function getPersonaJobs(personaId: string): Promise<TrainingJob[]> {
    try {
      const result = await authFetch<{ jobs: TrainingJob[] }>(
        `/api/ml-training/persona/${personaId}/jobs`
      );
      return result?.jobs || [];
    } catch (e: any) {
      console.error('Failed to fetch persona jobs:', e);
      return [];
    }
  }

  async function cancelTraining(jobId: string): Promise<boolean> {
    try {
      await authFetch(`/api/ml-training/jobs/${jobId}/cancel`, { method: 'POST' });
      return true;
    } catch (e: any) {
      console.error('Failed to cancel training:', e);
      return false;
    }
  }

  async function runInference(
    personaId: string,
    prompt: string,
    maxTokens?: number,
    temperature?: number
  ): Promise<InferenceResult | null> {
    try {
      return await authFetch<InferenceResult>('/api/ml-training/inference', {
        method: 'POST',
        body: { personaId, prompt, maxTokens, temperature },
      });
    } catch (e: any) {
      console.error('Failed to run inference:', e);
      return null;
    }
  }

  function streamTrainingProgress(
    jobId: string,
    onUpdate: (job: TrainingJob) => void
  ): () => void {
    // EventSource doesn't support custom headers, pass token as query param
    const { getAccessToken } = useAuth();
    const token = getAccessToken();
    const url = token
      ? `/api/ml-training/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`
      : `/api/ml-training/jobs/${jobId}/stream`;
    const es = new EventSource(url);

    const refreshJobOnClose = async () => {
      const job = await getTrainingJob(jobId);
      if (job) onUpdate(job);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          console.error('Training stream error:', data.error);
          es.close();
          refreshJobOnClose();
          return;
        }
        onUpdate(data as TrainingJob);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
      refreshJobOnClose();
    };

    // Return cleanup function
    return () => es.close();
  }

  async function fetchModels(): Promise<AvailableModel[]> {
    try {
      const result = await authFetch<{ models: AvailableModel[] }>('/api/ml-training/models');
      return result?.models || [];
    } catch (e: any) {
      console.error('Failed to fetch models:', e);
      return [];
    }
  }

  return {
    startTraining,
    getTrainingJob,
    getPersonaJobs,
    cancelTraining,
    runInference,
    streamTrainingProgress,
    fetchModels,
  };
}
