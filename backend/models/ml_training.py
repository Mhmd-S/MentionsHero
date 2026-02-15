"""ML Training Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

AVAILABLE_MODELS = [
    {"id": "mlx-community/Llama-3.2-3B-Instruct-4bit", "label": "Llama 3.2 3B Instruct (4-bit)", "params": "3B", "ram": "~2GB"},
    {"id": "mlx-community/Llama-3.2-1B-Instruct-4bit", "label": "Llama 3.2 1B Instruct (4-bit)", "params": "1B", "ram": "~1GB"},
    {"id": "mlx-community/Mistral-7B-Instruct-v0.3-4bit", "label": "Mistral 7B Instruct v0.3 (4-bit)", "params": "7B", "ram": "~4GB"},
    {"id": "mlx-community/gemma-2-2b-it-4bit", "label": "Gemma 2 2B IT (4-bit)", "params": "2B", "ram": "~1.5GB"},
    {"id": "mlx-community/Phi-3.5-mini-instruct-4bit", "label": "Phi 3.5 Mini Instruct (4-bit)", "params": "3.8B", "ram": "~2.5GB"},
]


class TrainingStatus(str, Enum):
    PENDING = "pending"
    PREPARING_DATA = "preparing_data"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StartTrainingRequest(BaseModel):
    persona_id: str = Field(alias="personaId")
    folder_id: str | None = Field(None, alias="folderId")
    # Model
    model: str | None = None
    # Training params
    iterations: int | None = None
    learning_rate: float | None = Field(None, alias="learningRate")
    batch_size: int | None = Field(None, alias="batchSize")
    max_seq_length: int | None = Field(None, alias="maxSeqLength")
    grad_accumulation_steps: int | None = Field(None, alias="gradAccumulationSteps")
    # LoRA params
    lora_rank: int | None = Field(None, alias="loraRank")
    lora_layers: int | None = Field(None, alias="loraLayers")
    lora_dropout: float | None = Field(None, alias="loraDropout")
    lora_scale: float | None = Field(None, alias="loraScale")
    # Data preprocessing params
    min_word_count: int | None = Field(None, alias="minWordCount")
    max_tokens: int | None = Field(None, alias="maxTokens")

    class Config:
        populate_by_name = True


class StartTrainingResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    status: TrainingStatus

    class Config:
        populate_by_name = True


class TrainingJob(BaseModel):
    id: str
    persona_id: str
    status: TrainingStatus
    stage_progress: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    total_segments: int = 0
    train_segments: int = 0
    valid_segments: int = 0
    test_segments: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    adapter_path: str | None = None
    data_path: str | None = None
    final_train_loss: float | None = None
    final_valid_loss: float | None = None
    training_duration_seconds: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: bool = False

    class Config:
        from_attributes = True


class InferenceRequest(BaseModel):
    persona_id: str = Field(alias="personaId")
    prompt: str
    max_tokens: int = Field(200, alias="maxTokens")
    temperature: float = 0.7

    class Config:
        populate_by_name = True


class InferenceResponse(BaseModel):
    persona_id: str = Field(alias="personaId")
    prompt: str
    completion: str
    tokens_generated: int = Field(alias="tokensGenerated")

    class Config:
        populate_by_name = True
