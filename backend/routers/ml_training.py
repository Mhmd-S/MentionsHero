"""ML Training API routes."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.ml_training import (
    AVAILABLE_MODELS,
    InferenceRequest,
    InferenceResponse,
    StartTrainingRequest,
    StartTrainingResponse,
    TrainingStatus,
)
from backend.services import ml_training_service

router = APIRouter(prefix="/api/ml-training", tags=["ml-training"])


@router.get("/models")
async def list_models():
    """List available MLX-compatible models."""
    return {"models": AVAILABLE_MODELS}


@router.post("/train")
async def start_training(
    request: StartTrainingRequest,
    background_tasks: BackgroundTasks,
) -> StartTrainingResponse:
    """Start a LoRA training job for a persona."""
    config_overrides = {
        k: v for k, v in request.model_dump(
            exclude={"persona_id", "folder_id"}, exclude_none=True
        ).items()
    }

    job = await ml_training_service.create_training_job(
        persona_id=request.persona_id,
        config=config_overrides if config_overrides else None,
    )

    background_tasks.add_task(
        ml_training_service.run_training_pipeline,
        job["id"],
        request.persona_id,
        request.folder_id,
    )

    return StartTrainingResponse(jobId=job["id"], status=TrainingStatus(job["status"]))


@router.get("/jobs/{job_id}")
async def get_training_job(job_id: str) -> dict[str, Any]:
    """Get a training job by ID."""
    job = await ml_training_service.get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job


@router.get("/jobs/{job_id}/stream")
async def stream_training_job(job_id: str):
    """Stream training job progress via SSE."""
    job_event = ml_training_service.get_training_job_event(job_id)
    wait_timeout = 5.0

    async def event_generator():
        last_status = ""
        last_progress = ""

        while True:
            try:
                job = await ml_training_service.get_training_job(job_id)
                if not job:
                    yield f"data: {json.dumps({'error': 'Training job not found'})}\n\n"
                    break

                current_progress = json.dumps(job.get("stage_progress", {}))
                if job.get("status") != last_status or current_progress != last_progress:
                    last_status = job.get("status")
                    last_progress = current_progress
                    yield f"data: {json.dumps(job)}\n\n"

                terminal = [
                    TrainingStatus.COMPLETED.value,
                    TrainingStatus.FAILED.value,
                    TrainingStatus.CANCELLED.value,
                ]
                if job.get("status") in terminal:
                    break

                job_event.clear()
                await asyncio.to_thread(job_event.wait, wait_timeout)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception:
                yield f"data: {json.dumps({'error': 'Failed to fetch training job'})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/persona/{persona_id}/jobs")
async def list_persona_jobs(persona_id: str) -> dict[str, list[dict[str, Any]]]:
    """List training jobs for a persona."""
    jobs = await ml_training_service.get_persona_jobs(persona_id)
    return {"jobs": jobs}


@router.post("/jobs/{job_id}/cancel")
async def cancel_training_job(job_id: str) -> dict[str, Any]:
    """Request cancellation of a training job."""
    success, message = await ml_training_service.request_cancellation(job_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/inference")
async def run_inference(request: InferenceRequest) -> InferenceResponse:
    """Run inference with a persona's trained LoRA adapter."""
    try:
        result = await ml_training_service.run_inference(
            persona_id=request.persona_id,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return InferenceResponse(
            personaId=result["persona_id"],
            prompt=result["prompt"],
            completion=result["completion"],
            tokensGenerated=result["tokens_generated"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
