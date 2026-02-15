"""ML Training service — job management, MLX LoRA training, and inference."""

import asyncio
import collections
import os
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any

# Jobs stuck in any non-terminal status with no progress for this long are marked failed (ghost jobs)
STALE_JOB_THRESHOLD_MINUTES = 30
# When cancelling, if job has had no progress for this long we treat it as inactive and mark cancelled immediately
INACTIVE_FOR_CANCEL_MINUTES = 5

import yaml

from backend.core.database import get_supabase
from backend.models.ml_training import TrainingStatus
from backend.services import ml_processing_service

# Statuses that are not terminal; if updated_at is too old, job is considered stale/ghost
NON_TERMINAL_STATUSES = (
    TrainingStatus.PENDING.value,
    TrainingStatus.PREPARING_DATA.value,
    TrainingStatus.TRAINING.value,
    TrainingStatus.EVALUATING.value,
)

# ---------- SSE notification events (same pattern as job_service) ----------

_job_events: dict[str, threading.Event] = {}


def _get_job_event(job_id: str) -> threading.Event:
    if job_id not in _job_events:
        _job_events[job_id] = threading.Event()
    return _job_events[job_id]


def notify_training_job_changed(job_id: str) -> None:
    _get_job_event(job_id).set()


def get_training_job_event(job_id: str) -> threading.Event:
    return _get_job_event(job_id)


# ---------- Config loading ----------

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "configs", "ml_default.yaml")


def load_default_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ---------- DB helpers ----------

async def create_training_job(persona_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    supabase = get_supabase()
    defaults = load_default_config()
    merged = {**defaults, **(config or {})}

    response = supabase.table("ml_training_jobs").insert({
        "persona_id": persona_id,
        "status": TrainingStatus.PENDING.value,
        "config": merged,
        "stage_progress": {},
    }).execute()

    return response.data[0]


def _parse_updated_at(job: dict[str, Any]) -> datetime | None:
    raw = job.get("updated_at")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _is_stale(job: dict[str, Any]) -> bool:
    """True if job is non-terminal and has had no progress for too long (ghost job)."""
    status = job.get("status")
    if status not in NON_TERMINAL_STATUSES:
        return False
    updated = _parse_updated_at(job)
    if not updated:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - updated) > timedelta(minutes=STALE_JOB_THRESHOLD_MINUTES)


def _no_progress_for_minutes(job: dict[str, Any], minutes: int) -> bool:
    """True if job is non-terminal and updated_at is older than the given minutes."""
    status = job.get("status")
    if status not in NON_TERMINAL_STATUSES:
        return False
    updated = _parse_updated_at(job)
    if not updated:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - updated) > timedelta(minutes=minutes)


async def _ensure_job_not_stale(job: dict[str, Any] | None) -> dict[str, Any] | None:
    """If job is stuck in pending/training too long, mark failed and return updated job."""
    if not job or not _is_stale(job):
        return job
    job_id = job.get("id")
    if not job_id:
        return job
    await update_training_progress(
        job_id,
        TrainingStatus.FAILED,
        error_message="Job timed out (no progress for too long). It may have been abandoned or the process stopped.",
    )
    return await get_training_job_raw(job_id)


async def get_training_job_raw(job_id: str) -> dict[str, Any] | None:
    supabase = get_supabase()
    response = supabase.table("ml_training_jobs").select("*").eq("id", job_id).single().execute()
    return response.data


async def get_training_job(job_id: str) -> dict[str, Any] | None:
    job = await get_training_job_raw(job_id)
    return await _ensure_job_not_stale(job)


async def get_persona_jobs_raw(persona_id: str) -> list[dict[str, Any]]:
    supabase = get_supabase()
    response = (
        supabase.table("ml_training_jobs")
        .select("*")
        .eq("persona_id", persona_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


async def get_latest_training_job(persona_id: str) -> dict[str, Any] | None:
    supabase = get_supabase()
    response = (
        supabase.table("ml_training_jobs")
        .select("*")
        .eq("persona_id", persona_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


async def get_persona_jobs(persona_id: str) -> list[dict[str, Any]]:
    raw_list = await get_persona_jobs_raw(persona_id)
    out = []
    for job in raw_list:
        fixed = await _ensure_job_not_stale(job)
        if fixed:
            out.append(fixed)
    return out


async def update_training_progress(
    job_id: str,
    status: TrainingStatus,
    stage_progress: dict[str, Any] | None = None,
    error_message: str | None = None,
    **extra: Any,
) -> None:
    supabase = get_supabase()

    update_data: dict[str, Any] = {
        "status": status.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if stage_progress is not None:
        update_data["stage_progress"] = stage_progress
    if error_message is not None:
        update_data["error_message"] = error_message

    for key in ("total_segments", "train_segments", "valid_segments", "test_segments",
                "adapter_path", "data_path", "final_train_loss", "final_valid_loss",
                "training_duration_seconds", "completed_at"):
        if key in extra:
            update_data[key] = extra[key]

    supabase.table("ml_training_jobs").update(update_data).eq("id", job_id).execute()
    notify_training_job_changed(job_id)


async def check_cancellation(job_id: str) -> bool:
    supabase = get_supabase()
    response = (
        supabase.table("ml_training_jobs")
        .select("cancel_requested")
        .eq("id", job_id)
        .single()
        .execute()
    )
    return response.data.get("cancel_requested", False) if response.data else False


async def request_cancellation(job_id: str) -> tuple[bool, str]:
    """
    Request cancellation of a training job.
    Returns (success, message). If job is not active (already terminal or inactive ghost),
    success is False and message explains why.
    """
    job = await get_training_job(job_id)
    if not job:
        return False, "Job not found"

    terminal = [TrainingStatus.COMPLETED.value, TrainingStatus.FAILED.value, TrainingStatus.CANCELLED.value]
    if job.get("status") in terminal:
        return False, "Job is not active (already completed, failed, or cancelled)"

    # Job is pending/training but has had no progress for a while -> treat as inactive ghost
    if _no_progress_for_minutes(job, INACTIVE_FOR_CANCEL_MINUTES):
        await mark_job_cancelled(job_id)
        return True, "Job was not active; marked as cancelled"

    supabase = get_supabase()
    supabase.table("ml_training_jobs").update({
        "cancel_requested": True,
    }).eq("id", job_id).execute()
    notify_training_job_changed(job_id)
    return True, "Cancellation requested"


async def mark_job_cancelled(job_id: str) -> None:
    supabase = get_supabase()
    supabase.table("ml_training_jobs").update({
        "status": TrainingStatus.CANCELLED.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()
    notify_training_job_changed(job_id)


# ---------- Training pipeline ----------

async def run_training_pipeline(
    job_id: str,
    persona_id: str,
    folder_id: str | None = None,
) -> None:
    """Full pipeline: prepare data → train LoRA → mark complete."""
    start_time = time.time()
    process: asyncio.subprocess.Process | None = None

    try:
        job = await get_training_job(job_id)
        if not job:
            raise ValueError(f"Training job {job_id} not found")

        config = job.get("config", {})
        base_dir = os.path.join(os.getcwd(), "models", "personas", persona_id)
        data_dir = os.path.join(base_dir, "data")
        adapter_dir = os.path.join(base_dir, "adapters")

        # --- Stage 1: Prepare data ---
        if await check_cancellation(job_id):
            await mark_job_cancelled(job_id)
            return

        await update_training_progress(
            job_id, TrainingStatus.PREPARING_DATA,
            stage_progress={"stage": "preparing_data", "detail": "Extracting persona segments", "elapsed_seconds": 0},
        )

        loop = asyncio.get_running_loop()

        def _data_prep_progress(msg: str) -> None:
            elapsed = int(time.time() - start_time)
            coro = update_training_progress(
                job_id, TrainingStatus.PREPARING_DATA,
                stage_progress={"stage": "preparing_data", "detail": msg, "elapsed_seconds": elapsed},
            )
            asyncio.run_coroutine_threadsafe(coro, loop)

        data_result = await ml_processing_service.prepare_training_data(
            persona_id=persona_id,
            output_dir=data_dir,
            folder_id=folder_id,
            min_word_count=config.get("min_word_count", 20),
            max_tokens=config.get("max_tokens", 480),
            on_progress=_data_prep_progress,
        )

        await update_training_progress(
            job_id, TrainingStatus.PREPARING_DATA,
            stage_progress={
                "stage": "preparing_data",
                "detail": f"Found {data_result['total_segments']} segments",
                "elapsed_seconds": int(time.time() - start_time),
            },
            total_segments=data_result["total_segments"],
            train_segments=data_result["train_segments"],
            valid_segments=data_result["valid_segments"],
            test_segments=data_result["test_segments"],
            data_path=data_dir,
        )

        # --- Stage 2: Write LoRA config and run training ---
        if await check_cancellation(job_id):
            await mark_job_cancelled(job_id)
            return

        os.makedirs(adapter_dir, exist_ok=True)
        lora_config = {
            "model": config.get("model", "mlx-community/Llama-3.2-3B-Instruct-4bit"),
            "train": True,
            "data": data_dir,
            "adapter-path": adapter_dir,
            "lora-layers": config.get("lora_layers", config.get("num_layers", 18)),
            "batch-size": config.get("batch_size", 1),
            "iters": config.get("iterations", 750),
            "val-batches": 25,
            "learning-rate": config.get("learning_rate", 5e-5),
            "steps-per-report": 10,
            "steps-per-eval": 100,
            "max-seq-length": config.get("max_seq_length", 1024),
            "grad-checkpoint": True,
            "grad-accumulation-steps": config.get("grad_accumulation_steps", 4),
            "lora_parameters": {
                "rank": config.get("lora_rank", 16),
                "dropout": config.get("lora_dropout", 0.0),
                "scale": config.get("lora_scale", 10.0),
            },
        }

        config_path = os.path.join(adapter_dir, "lora_config.yaml")
        with open(config_path, "w") as f:
            yaml.dump(lora_config, f)

        await update_training_progress(
            job_id, TrainingStatus.TRAINING,
            stage_progress={
                "stage": "training",
                "iteration": 0,
                "total_iterations": lora_config["iters"],
                "train_loss": None,
                "valid_loss": None,
                "elapsed_seconds": int(time.time() - start_time),
                "output": [],
            },
        )

        # Run mlx_lm.lora as subprocess
        cmd = [
            "python3", "-m", "mlx_lm.lora",
            "--config", config_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # Parse stdout for progress
        iteration_re = re.compile(r"Iter\s+(\d+).*Train loss\s+([\d.]+)")
        valid_re = re.compile(r"Iter\s+(\d+).*Val loss\s+([\d.]+)")
        latest_train_loss: float | None = None
        latest_valid_loss: float | None = None
        recent_lines: collections.deque[str] = collections.deque(maxlen=500)
        latest_iteration = 0
        loss_history: list[dict[str, Any]] = []
        training_stage_start = time.time()

        def _calc_eta() -> float | None:
            if latest_iteration <= 0:
                return None
            elapsed_training = time.time() - training_stage_start
            remaining = lora_config["iters"] - latest_iteration
            return (elapsed_training / latest_iteration) * remaining

        def _build_stage_progress() -> dict[str, Any]:
            return {
                "stage": "training",
                "iteration": latest_iteration,
                "total_iterations": lora_config["iters"],
                "train_loss": latest_train_loss,
                "valid_loss": latest_valid_loss,
                "elapsed_seconds": int(time.time() - start_time),
                "eta_seconds": round(_calc_eta()) if _calc_eta() is not None else None,
                "loss_history": loss_history,
                "output": list(recent_lines),
            }

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            recent_lines.append(line)
            m_train = iteration_re.search(line)
            m_valid = valid_re.search(line)

            if m_train:
                latest_iteration = int(m_train.group(1))
                latest_train_loss = float(m_train.group(2))
                loss_history.append({
                    "iter": latest_iteration,
                    "train_loss": latest_train_loss,
                    "valid_loss": latest_valid_loss,
                })

            if m_valid:
                latest_valid_loss = float(m_valid.group(2))
                # Update the last history entry with valid loss if same iteration
                if loss_history and loss_history[-1]["iter"] == latest_iteration:
                    loss_history[-1]["valid_loss"] = latest_valid_loss

            # Push SSE on every line so all output appears in real-time
            await update_training_progress(
                job_id, TrainingStatus.TRAINING,
                stage_progress=_build_stage_progress(),
            )

            # Check cancellation periodically
            if await check_cancellation(job_id):
                process.terminate()
                await process.wait()
                await mark_job_cancelled(job_id)
                return

        return_code = await process.wait()
        process = None

        if return_code != 0:
            raise RuntimeError(f"mlx_lm.lora exited with code {return_code}")

        # --- Stage 3: Mark complete ---
        elapsed = int(time.time() - start_time)

        # Update persona
        supabase = get_supabase()
        supabase.table("personas").update({
            "has_model": True,
            "last_trained_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", persona_id).execute()

        await update_training_progress(
            job_id, TrainingStatus.COMPLETED,
            stage_progress={"stage": "completed"},
            adapter_path=adapter_dir,
            final_train_loss=latest_train_loss,
            final_valid_loss=latest_valid_loss,
            training_duration_seconds=elapsed,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        if process is not None:
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass

        try:
            await update_training_progress(
                job_id, TrainingStatus.FAILED,
                stage_progress={"stage": "failed"},
                error_message=str(e),
            )
        except Exception:
            # Last resort: try a direct DB update so the job doesn't stay stuck
            try:
                supabase = get_supabase()
                supabase.table("ml_training_jobs").update({
                    "status": TrainingStatus.FAILED.value,
                    "error_message": str(e)[:500],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", job_id).execute()
            except Exception:
                pass


# ---------- Inference ----------

async def run_inference(
    persona_id: str,
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Run inference using base model + persona LoRA adapter."""
    adapter_dir = os.path.join(os.getcwd(), "models", "personas", persona_id, "adapters")
    if not os.path.exists(adapter_dir):
        raise ValueError(f"No trained model found for persona {persona_id}")

    # Use the model from the latest completed job, falling back to default config
    latest_job = await get_latest_training_job(persona_id)
    if latest_job and latest_job.get("status") == "completed" and latest_job.get("config"):
        model_name = latest_job["config"].get("model", "mlx-community/Llama-3.2-3B-Instruct-4bit")
    else:
        config = load_default_config()
        model_name = config.get("model", "mlx-community/Llama-3.2-3B-Instruct-4bit")

    from mlx_lm import load, generate  # type: ignore[import-untyped]

    model, tokenizer = load(model_name, adapter_path=adapter_dir)
    result = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        temp=temperature,
    )

    return {
        "persona_id": persona_id,
        "prompt": prompt,
        "completion": result,
        "tokens_generated": len(tokenizer.encode(result)),
    }
