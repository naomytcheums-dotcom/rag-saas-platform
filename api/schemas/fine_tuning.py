"""Partie 24 -- request/response bodies for api/routers/fine_tuning.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class FineTuningDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID | None
    name: str
    description: str | None
    dataset_type: str
    format: str
    size: int
    status: str
    validation_errors: list | None
    example_count: int | None
    created_at: dt.datetime


class FineTuningDatasetListResponse(BaseModel):
    items: list[FineTuningDatasetResponse]
    total: int
    limit: int
    offset: int


class FineTuningJobCreateRequest(BaseModel):
    dataset_id: uuid.UUID
    name: str
    base_model: str | None = None
    provider: str | None = None
    hyperparameters: dict | None = None


class FineTuningJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    dataset_id: uuid.UUID
    created_by: uuid.UUID | None
    name: str
    base_model: str
    provider: str
    status: str
    hyperparameters: dict
    metrics: dict
    provider_job_id: str | None
    error_message: str | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    created_at: dt.datetime


class FineTuningJobListResponse(BaseModel):
    items: list[FineTuningJobResponse]
    total: int
    limit: int
    offset: int


class FineTunedModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    job_id: uuid.UUID
    name: str
    provider: str
    provider_model_id: str
    base_model: str
    status: str
    deployed: bool
    metrics: dict
    created_at: dt.datetime


class FineTunedModelListResponse(BaseModel):
    items: list[FineTunedModelResponse]
    total: int
    limit: int
    offset: int


class FineTuningEvaluateRequest(BaseModel):
    dataset_id: uuid.UUID


class FineTuningEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_id: uuid.UUID
    dataset_id: uuid.UUID
    evaluation_job_id: uuid.UUID | None
    metrics: dict
    score: float | None
    created_at: dt.datetime
