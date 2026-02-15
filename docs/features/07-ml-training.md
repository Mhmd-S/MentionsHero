# ML Training

## Purpose
Per-persona LoRA fine-tuning on Apple Silicon via MLX. Extracts a persona's speech segments from transcripts, trains a small language model adapter, and provides an inference endpoint to generate text in the persona's style.

## User Flow
1. User navigates to `/model` and selects a persona
2. Configures training: model selection, folder scope, data preprocessing params, training hyperparams, LoRA params
3. Clicks "Train Model" — job created, training starts
4. Real-time progress via SSE: preparing data → training (iteration/loss updates) → completed
5. On completion, views segment stats, final losses, training duration
6. Tests the model with a prompt in the test modal
7. Can retrain with different parameters

## Data Flow

```
model.vue → selects persona → renders ModelTrainingPanel

ModelTrainingPanel.vue
  → useMLTraining().startTraining(personaId, folderId, config)
    → POST /api/ml-training/train { personaId, folderId?, config overrides }
      → ml_training_service.create_training_job()
        → INSERT ml_training_jobs with merged config
      → BackgroundTask: run_training_pipeline(job_id, persona_id, folder_id)

run_training_pipeline():
  Stage 1 — PREPARING_DATA:
    → ml_processing_service.prepare_training_data()
      → Get persona aliases
      → Fetch transcripts (optional folder scope)
      → Parse segments, match speakers to aliases
      → Filter by min_word_count and max_tokens
      → Split 80/10/10 → write train.jsonl, valid.jsonl, test.jsonl
    → Update job with segment counts

  Stage 2 — TRAINING:
    → Write lora_config.yaml to models/personas/{id}/adapters/
    → Subprocess: python3 -m mlx_lm.lora --config lora_config.yaml
    → Parse stdout regex for iteration and loss values
    → Update DB + notify SSE on each iteration
    → Check cancellation between output lines

  Stage 3 — COMPLETED:
    → Update persona: has_model=true, last_trained_at=now()
    → Save final losses, duration, adapter_path

Frontend SSE:
  → useMLTraining().streamTrainingProgress(jobId, onUpdate)
    → EventSource → GET /api/ml-training/jobs/{jobId}/stream?token={jwt}
    → Updates progress bar, iteration count, losses, output log

Inference:
  → useMLTraining().runInference(personaId, prompt)
    → POST /api/ml-training/inference { personaId, prompt, maxTokens, temperature }
      → ml_training_service.run_inference()
        → mlx_lm.load(model_id, adapter_path)
        → mlx_lm.generate(model, tokenizer, prompt, max_tokens, temp)
      → Returns { completion, tokensGenerated }
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/model.vue` | ML model landing page — persona selector, renders ModelTrainingPanel |
| `app/pages/personas/[id]/model.vue` | Redirect helper — redirects to `/model?persona={id}` |
| `app/components/ModelTrainingPanel.vue` | Full training UI — config form, progress display, inference test modal |
| `app/composables/useMLTraining.ts` | `startTraining()`, `getTrainingJob()`, `cancelTraining()`, `runInference()`, `streamTrainingProgress()`, `fetchModels()` |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/ml_training.py` | Endpoints: train, job CRUD, SSE stream, cancel, inference, list models |
| `backend/services/ml_training_service.py` | Job lifecycle, training pipeline, subprocess management, SSE events, inference |
| `backend/services/ml_processing_service.py` | `prepare_training_data()` — transcript parsing, segment extraction, JSONL splits |
| `backend/models/ml_training.py` | TrainingStatus enum, StartTrainingRequest, TrainingJob, InferenceRequest, AVAILABLE_MODELS |
| `backend/configs/ml_default.yaml` | Default hyperparameters (model, iterations, learning_rate, LoRA params) |

## Database Tables
- **ml_training_jobs** — job tracking with stage_progress JSONB, config JSONB, segment counts, losses, adapter_path, data_path
- **personas** — `has_model` (boolean), `last_trained_at` (timestamptz) columns added by ML migration

## External Integrations
- **MLX framework** (`mlx_lm`) — Apple Silicon ML library for LoRA fine-tuning and inference
- **HuggingFace MLX Community** — quantized model weights (4-bit)

### Available Models
| Model | Params | RAM |
|-------|--------|-----|
| Llama 3.2 3B Instruct (4-bit) | 3B | ~2GB |
| Llama 3.2 1B Instruct (4-bit) | 1B | ~1GB |
| Mistral 7B Instruct v0.3 (4-bit) | 7B | ~4GB |
| Gemma 2 2B IT (4-bit) | 2B | ~1.5GB |
| Phi 3.5 Mini Instruct (4-bit) | 3.8B | ~2.5GB |

## Key Implementation Details

**Training config** (defaults from `ml_default.yaml`):
- Model: `mlx-community/Llama-3.2-3B-Instruct-4bit`
- Iterations: 750, Learning rate: 5e-5, Batch size: 1
- Max seq length: 1024, Grad accumulation: 4
- LoRA: rank=16, layers=18, dropout=0.0, scale=10.0
- Data: min_word_count=20, max_tokens=480

**File system layout:**
```
models/personas/{persona_id}/
├── data/
│   ├── train.jsonl    # 80% of segments
│   ├── valid.jsonl    # 10%
│   └── test.jsonl     # 10%
└── adapters/
    ├── lora_config.yaml
    └── [MLX adapter weights]
```

**Progress parsing & streaming:** Every stdout line from the subprocess triggers an SSE push, so model loading messages, tokenizer info, and warnings all appear in the terminal in real-time. Regex matches extract structured data:
- `Iter\s+(\d+).*Train loss\s+([\d.]+)` → updates train_loss, iteration, appends to loss_history
- `Iter\s+(\d+).*Val loss\s+([\d.]+)` → updates valid_loss, patches latest loss_history entry
- 500-line output buffer maintained for terminal display
- `loss_history` accumulates `{ iter, train_loss, valid_loss }` entries for chart rendering
- `eta_seconds` computed as `(elapsed / current_iter) * remaining_iters`

**`stage_progress` shape (training stage):**
```json
{
  "stage": "training",
  "iteration": 100,
  "total_iterations": 750,
  "train_loss": 2.45,
  "valid_loss": 2.68,
  "elapsed_seconds": 300,
  "eta_seconds": 1950,
  "loss_history": [
    { "iter": 10, "train_loss": 3.2, "valid_loss": null },
    { "iter": 20, "train_loss": 2.9, "valid_loss": null },
    { "iter": 100, "train_loss": 2.45, "valid_loss": 2.68 }
  ],
  "output": ["Loading model...", "Iter 10: Train loss 3.200...", "..."]
}
```

**Cancellation:** Cooperative — checks `cancel_requested` flag between stdout lines. Terminates subprocess on cancellation.

**Stale job detection:** Jobs with no `updated_at` change for 30+ minutes are auto-marked as failed on fetch.

**SSE:** 5-second timeout with `threading.Event` for instant wake. Emits full job object when state changes.

**Job states:** `pending → preparing_data → training → evaluating → completed | failed | cancelled`
