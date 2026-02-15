<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'
import { useFileTree } from '~/composables/useFileTree'
import { useMLTraining, type TrainingJob, type AvailableModel } from '~/composables/useMLTraining'

const props = defineProps<{
  personaId: string
}>()

const { getPersona } = usePersonas()
const { folders, fetchFolders } = useFileTree()
const { startTraining, getPersonaJobs, cancelTraining, runInference, streamTrainingProgress, fetchModels } = useMLTraining()

const persona = ref<Awaited<ReturnType<typeof getPersona>>>(null)
const loadingPersona = ref(true)

const latestJob = ref<TrainingJob | null>(null)
const loadingML = ref(false)
const showTrainModal = ref(false)
const showTestModal = ref(false)
const trainingInProgress = ref(false)
const availableModels = ref<AvailableModel[]>([])
const trainModel = ref<string | undefined>(undefined)
const trainFolderId = ref<string | undefined>(undefined)
const trainIterations = ref<number | undefined>(undefined)
const trainLearningRate = ref<number | undefined>(undefined)
const trainBatchSize = ref<number | undefined>(undefined)
const trainMaxSeqLength = ref<number | undefined>(undefined)
const trainGradAccumulationSteps = ref<number | undefined>(undefined)
const trainLoraRank = ref<number | undefined>(undefined)
const trainLoraLayers = ref<number | undefined>(undefined)
const trainLoraDropout = ref<number | undefined>(undefined)
const trainLoraScale = ref<number | undefined>(undefined)
const trainMinWordCount = ref<number | undefined>(undefined)
const trainMaxTokens = ref<number | undefined>(undefined)
const showDataSection = ref(false)
const showTrainingSection = ref(false)
const showLoraSection = ref(false)
const showOutputLog = ref(false)
const showConfigSection = ref(false)
let stopStream: (() => void) | null = null
const outputLogEl = ref<HTMLElement | null>(null)

const inferencePrompt = ref('')
const inferenceResult = ref('')
const inferenceLoading = ref(false)

const folderOptions = computed(() =>
  folders.value.filter(f => !f.parent_id).map(f => ({ label: f.name, value: f.id }))
)

const modelOptions = computed(() =>
  availableModels.value.map(m => ({ label: `${m.label} (${m.ram})`, value: m.id }))
)

const trainingProgress = computed(() => {
  if (!latestJob.value) return null
  const sp = latestJob.value.stage_progress || {}
  return {
    stage: sp.stage || latestJob.value.status,
    iteration: sp.iteration || 0,
    totalIterations: sp.total_iterations || 0,
    trainLoss: sp.train_loss,
    validLoss: sp.valid_loss,
    detail: sp.detail || '',
    elapsedSeconds: sp.elapsed_seconds ?? null,
    output: sp.output || [],
  }
})

const shortModelName = computed(() => {
  const model = latestJob.value?.config?.model
  if (!model) return null
  return model.replace('mlx-community/', '')
})

const configEntries = computed(() => {
  const c = latestJob.value?.config
  if (!c) return []
  const keys = ['iterations', 'learning_rate', 'batch_size', 'max_seq_length', 'lora_rank', 'lora_layers', 'lora_dropout', 'lora_scale', 'grad_accumulation_steps', 'min_word_count', 'max_tokens']
  return keys.filter(k => c[k] != null).map(k => ({ key: k.replace(/_/g, ' '), value: c[k] }))
})

const progressPercent = computed(() => {
  const p = trainingProgress.value
  if (!p || !p.totalIterations) return 0
  return Math.round((p.iteration / p.totalIterations) * 100)
})

const isTerminal = computed(() => {
  if (!latestJob.value) return true
  return ['completed', 'failed', 'cancelled'].includes(latestJob.value.status)
})

async function loadLatestJob() {
  loadingML.value = true
  try {
    const jobs = await getPersonaJobs(props.personaId)
    latestJob.value = jobs[0] ?? null

    if (latestJob.value && !isTerminal.value) {
      trainingInProgress.value = true
      startJobStream(latestJob.value.id)
    }
  } finally {
    loadingML.value = false
  }
}

function startJobStream(jobId: string) {
  if (stopStream) stopStream()
  stopStream = streamTrainingProgress(jobId, (job) => {
    latestJob.value = job ?? null
    if (job && ['completed', 'failed', 'cancelled'].includes(job.status)) {
      trainingInProgress.value = false
      if (stopStream) {
        stopStream()
        stopStream = null
      }
      getPersona(props.personaId).then(p => { persona.value = p })
    }
  })
}

function prefillFromLastJob() {
  if (!latestJob.value?.config) return
  const c = latestJob.value.config
  trainModel.value = c.model
  trainIterations.value = c.iterations
  trainLearningRate.value = c.learning_rate
  trainBatchSize.value = c.batch_size
  trainMaxSeqLength.value = c.max_seq_length
  trainGradAccumulationSteps.value = c.grad_accumulation_steps
  trainLoraRank.value = c.lora_rank
  trainLoraLayers.value = c.lora_layers ?? c.num_layers
  trainLoraDropout.value = c.lora_dropout
  trainLoraScale.value = c.lora_scale
  trainMinWordCount.value = c.min_word_count
  trainMaxTokens.value = c.max_tokens
}

function resetTrainForm() {
  trainModel.value = undefined
  trainFolderId.value = undefined
  trainIterations.value = undefined
  trainLearningRate.value = undefined
  trainBatchSize.value = undefined
  trainMaxSeqLength.value = undefined
  trainGradAccumulationSteps.value = undefined
  trainLoraRank.value = undefined
  trainLoraLayers.value = undefined
  trainLoraDropout.value = undefined
  trainLoraScale.value = undefined
  trainMinWordCount.value = undefined
  trainMaxTokens.value = undefined
}

function openTrainModal() {
  if (latestJob.value?.status === 'completed') {
    prefillFromLastJob()
  } else {
    resetTrainForm()
  }
  showTrainModal.value = true
}

async function handleStartTraining() {
  const config: Record<string, any> = {}
  if (trainModel.value) config.model = trainModel.value
  if (trainIterations.value != null) config.iterations = trainIterations.value
  if (trainLearningRate.value != null) config.learningRate = trainLearningRate.value
  if (trainBatchSize.value != null) config.batchSize = trainBatchSize.value
  if (trainMaxSeqLength.value != null) config.maxSeqLength = trainMaxSeqLength.value
  if (trainGradAccumulationSteps.value != null) config.gradAccumulationSteps = trainGradAccumulationSteps.value
  if (trainLoraRank.value != null) config.loraRank = trainLoraRank.value
  if (trainLoraLayers.value != null) config.loraLayers = trainLoraLayers.value
  if (trainLoraDropout.value != null) config.loraDropout = trainLoraDropout.value
  if (trainLoraScale.value != null) config.loraScale = trainLoraScale.value
  if (trainMinWordCount.value != null) config.minWordCount = trainMinWordCount.value
  if (trainMaxTokens.value != null) config.maxTokens = trainMaxTokens.value

  const result = await startTraining(props.personaId, trainFolderId.value, config)
  if (result) {
    showTrainModal.value = false
    resetTrainForm()
    trainingInProgress.value = true
    await loadLatestJob()
  }
}

async function handleCancelTraining() {
  if (!latestJob.value) return
  try {
    await cancelTraining(latestJob.value.id)
  } finally {
    await loadLatestJob()
  }
}

async function handleRunInference() {
  if (!inferencePrompt.value.trim()) return
  inferenceLoading.value = true
  inferenceResult.value = ''
  try {
    const result = await runInference(props.personaId, inferencePrompt.value)
    if (result) {
      inferenceResult.value = result.completion
    }
  } finally {
    inferenceLoading.value = false
  }
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

async function loadForPersona(id: string) {
  if (stopStream) {
    stopStream()
    stopStream = null
  }
  latestJob.value = null
  loadingPersona.value = true
  try {
    persona.value = await getPersona(id)
  } finally {
    loadingPersona.value = false
  }
  await Promise.all([
    fetchFolders(),
    loadLatestJob(),
    fetchModels().then(m => { availableModels.value = m }),
  ])
}

watch(() => trainingProgress.value?.output, () => {
  if (showOutputLog.value && outputLogEl.value) {
    nextTick(() => {
      if (outputLogEl.value) {
        outputLogEl.value.scrollTop = outputLogEl.value.scrollHeight
      }
    })
  }
})

watch(() => props.personaId, (id) => {
  if (id) loadForPersona(id)
}, { immediate: false })

onMounted(() => {
  loadForPersona(props.personaId)
})

onUnmounted(() => {
  if (stopStream) stopStream()
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <div v-if="loadingPersona" class="flex items-center justify-center p-8">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="!persona" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      Persona not found.
    </div>

    <template v-else>
      <h2 class="text-xl font-semibold mb-1">ML Model — {{ persona.name }}</h2>
      <p class="text-gray-500 text-sm mb-6">
        Train a LoRA model on this persona's speech segments.
      </p>

      <div v-if="loadingML" class="flex items-center justify-center p-4">
        <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin" />
      </div>

      <div v-else-if="latestJob && !isTerminal" class="border rounded-lg p-4 space-y-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin text-primary" />
            <span class="text-sm font-medium capitalize">{{ trainingProgress?.stage?.replace('_', ' ') }}</span>
            <span v-if="trainingProgress?.elapsedSeconds != null" class="text-xs text-gray-400">{{ formatDuration(trainingProgress.elapsedSeconds) }}</span>
            <UBadge v-if="shortModelName" variant="subtle" size="xs">{{ shortModelName }}</UBadge>
          </div>
          <UButton size="xs" color="error" variant="soft" @click="handleCancelTraining">Cancel</UButton>
        </div>

        <div v-if="trainingProgress?.stage === 'training'" class="space-y-2">
          <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              class="bg-primary h-2 rounded-full transition-all duration-300"
              :style="{ width: `${progressPercent}%` }"
            />
          </div>
          <div class="flex justify-between text-xs text-gray-500">
            <span>Iteration {{ trainingProgress?.iteration }} / {{ trainingProgress?.totalIterations }}</span>
            <span>{{ progressPercent }}%</span>
          </div>
          <div v-if="trainingProgress?.trainLoss" class="text-xs text-gray-500">
            Train loss: {{ trainingProgress.trainLoss.toFixed(4) }}
            <span v-if="trainingProgress?.validLoss"> | Val loss: {{ trainingProgress.validLoss.toFixed(4) }}</span>
          </div>

          <div v-if="trainingProgress?.output?.length" class="mt-2">
            <button
              type="button"
              class="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              @click="showOutputLog = !showOutputLog"
            >
              <UIcon :name="showOutputLog ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-3 h-3" />
              Output Log
            </button>
            <pre
              v-if="showOutputLog"
              ref="outputLogEl"
              class="mt-1 text-xs font-mono bg-gray-50 dark:bg-gray-900 border rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap"
            >{{ trainingProgress.output.join('\n') }}</pre>
          </div>
        </div>

        <div v-else-if="trainingProgress?.detail" class="text-sm text-gray-500">
          {{ trainingProgress.detail }}
        </div>
      </div>

      <div v-else-if="latestJob?.status === 'completed'" class="border rounded-lg p-4 space-y-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <UBadge color="success" variant="soft">Model trained</UBadge>
            <UBadge v-if="shortModelName" variant="subtle" size="xs">{{ shortModelName }}</UBadge>
          </div>
          <div class="flex gap-2">
            <UButton size="sm" variant="soft" @click="showTestModal = true">Test Model</UButton>
            <UButton size="sm" variant="outline" @click="openTrainModal()">Retrain</UButton>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
          <div>
            <div class="text-gray-500 text-xs">Segments</div>
            <div class="font-medium">{{ latestJob.total_segments }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">Train / Val / Test</div>
            <div class="font-medium">{{ latestJob.train_segments }} / {{ latestJob.valid_segments }} / {{ latestJob.test_segments }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">Train Loss</div>
            <div class="font-medium">{{ latestJob.final_train_loss?.toFixed(4) || '-' }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">Valid Loss</div>
            <div class="font-medium">{{ latestJob.final_valid_loss?.toFixed(4) || '-' }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">Duration</div>
            <div class="font-medium">{{ formatDuration(latestJob.training_duration_seconds) }}</div>
          </div>
        </div>

        <div v-if="configEntries.length">
          <button
            type="button"
            class="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            @click="showConfigSection = !showConfigSection"
          >
            <UIcon :name="showConfigSection ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-3 h-3" />
            Training Config
          </button>
          <div v-if="showConfigSection" class="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-xs">
            <div v-for="entry in configEntries" :key="entry.key" class="flex justify-between border-b border-gray-100 dark:border-gray-800 py-1">
              <span class="text-gray-500 capitalize">{{ entry.key }}</span>
              <span class="font-medium">{{ entry.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="latestJob?.status === 'failed'" class="border border-red-200 dark:border-red-800 rounded-lg p-4 space-y-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <UBadge color="error" variant="soft">Training failed</UBadge>
          </div>
          <UButton size="sm" @click="openTrainModal()">Retry</UButton>
        </div>
        <p v-if="latestJob.error_message" class="text-sm text-red-600 dark:text-red-400">{{ latestJob.error_message }}</p>
      </div>

      <div v-else class="text-gray-500 text-base p-4 border border-dashed rounded-lg flex items-center justify-between">
        <span>No ML model trained yet. Train a LoRA model on this persona's speech segments.</span>
        <UButton size="sm" @click="openTrainModal()">Train Model</UButton>
      </div>
    </template>

    <UModal v-model:open="showTrainModal">
      <template #content>
        <div class="p-6 max-h-[80vh] overflow-y-auto">
          <h3 class="text-lg font-semibold mb-4">Train ML Model</h3>
          <p class="text-sm text-gray-500 mb-4">
            Fine-tune a model on {{ persona?.name }}'s speech segments using LoRA.
          </p>

          <div class="space-y-4">
            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Base Model</label>
              <USelectMenu
                v-model="trainModel"
                :items="modelOptions"
                value-key="value"
                placeholder="Llama 3.2 3B Instruct (4-bit) — default"
                class="w-full"
              />
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Transcript Folder (optional)</label>
              <USelectMenu
                v-model="trainFolderId"
                :items="folderOptions"
                value-key="value"
                placeholder="All transcripts"
                class="w-full"
              />
            </div>

            <div class="border rounded-lg">
              <button
                type="button"
                class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
                @click="showDataSection = !showDataSection"
              >
                <span>Data Preprocessing</span>
                <UIcon :name="showDataSection ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-4 h-4" />
              </button>
              <div v-if="showDataSection" class="px-3 pb-3 space-y-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Min Word Count</label>
                    <UInput v-model.number="trainMinWordCount" type="number" placeholder="20" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Tokens per Segment</label>
                    <UInput v-model.number="trainMaxTokens" type="number" placeholder="480" />
                  </div>
                </div>
              </div>
            </div>

            <div class="border rounded-lg">
              <button
                type="button"
                class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
                @click="showTrainingSection = !showTrainingSection"
              >
                <span>Training Parameters</span>
                <UIcon :name="showTrainingSection ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-4 h-4" />
              </button>
              <div v-if="showTrainingSection" class="px-3 pb-3 space-y-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Iterations</label>
                    <UInput v-model.number="trainIterations" type="number" placeholder="750" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Learning Rate</label>
                    <UInput v-model.number="trainLearningRate" type="number" step="0.00001" placeholder="5e-5" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Batch Size</label>
                    <UInput v-model.number="trainBatchSize" type="number" placeholder="1" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Sequence Length</label>
                    <UInput v-model.number="trainMaxSeqLength" type="number" placeholder="1024" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Grad Accumulation Steps</label>
                    <UInput v-model.number="trainGradAccumulationSteps" type="number" placeholder="4" />
                  </div>
                </div>
              </div>
            </div>

            <div class="border rounded-lg">
              <button
                type="button"
                class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
                @click="showLoraSection = !showLoraSection"
              >
                <span>LoRA Parameters</span>
                <UIcon :name="showLoraSection ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-4 h-4" />
              </button>
              <div v-if="showLoraSection" class="px-3 pb-3 space-y-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Rank</label>
                    <UInput v-model.number="trainLoraRank" type="number" placeholder="16" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Layers</label>
                    <UInput v-model.number="trainLoraLayers" type="number" placeholder="18" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Dropout</label>
                    <UInput v-model.number="trainLoraDropout" type="number" step="0.01" placeholder="0.0" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Scale</label>
                    <UInput v-model.number="trainLoraScale" type="number" step="0.1" placeholder="10.0" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showTrainModal = false">Cancel</UButton>
            <UButton @click="handleStartTraining">Start Training</UButton>
          </div>
        </div>
      </template>
    </UModal>

    <UModal v-model:open="showTestModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Test Model - {{ persona?.name }}</h3>

          <div class="space-y-4">
            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Prompt</label>
              <UInput
                v-model="inferencePrompt"
                placeholder="Enter a prompt to generate speech..."
              />
            </div>

            <UButton :loading="inferenceLoading" :disabled="!inferencePrompt.trim()" @click="handleRunInference">
              Generate
            </UButton>

            <div v-if="inferenceResult" class="border rounded-lg p-4 bg-gray-50 dark:bg-gray-900">
              <p class="text-sm">
                <span class="text-gray-400">{{ inferencePrompt }}</span>
                <span class="font-medium">{{ inferenceResult }}</span>
              </p>
            </div>
          </div>

          <div class="flex justify-end mt-6">
            <UButton variant="ghost" @click="showTestModal = false; inferenceResult = ''; inferencePrompt = ''">Close</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
