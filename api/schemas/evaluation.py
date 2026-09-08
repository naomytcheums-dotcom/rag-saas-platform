"""Request/response bodies for api/routers/evaluation_datasets.py,
api/routers/question_sets.py, and api/routers/benchmark_versions.py
(Partie 7.1.1/7.1.2/7.1.6)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class DatasetCreateRequest(BaseModel):
    name: str
    description: str | None = None


class DatasetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    version: int
    is_active: bool
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int
    limit: int
    offset: int


class QuestionCreateRequest(BaseModel):
    question: str
    expected_answer: str | None = None
    expected_documents: list[dict] | None = None
    difficulty: str | None = None
    category: str | None = None


class QuestionUpdateRequest(BaseModel):
    question: str | None = None
    expected_answer: str | None = None
    expected_documents: list[dict] | None = None
    difficulty: str | None = None
    category: str | None = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    expected_answer: str | None
    expected_documents: list | None
    difficulty: str | None
    category: str | None
    metadata_json: dict | None
    expected_answer_type: str | None
    expected_answer_metadata: dict | None
    created_at: dt.datetime
    updated_at: dt.datetime


class QuestionListResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
    limit: int
    offset: int


class QuestionImportResponse(BaseModel):
    imported: int
    errors: list[str]


class QuestionSetCreateRequest(BaseModel):
    name: str
    description: str | None = None


class QuestionSetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class QuestionSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    description: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class QuestionSetListResponse(BaseModel):
    items: list[QuestionSetResponse]
    total: int
    limit: int
    offset: int


class AddQuestionToSetRequest(BaseModel):
    question_id: uuid.UUID
    position: int | None = None


class ReorderQuestionsRequest(BaseModel):
    question_ids: list[uuid.UUID]


class DuplicateQuestionSetRequest(BaseModel):
    new_name: str


class BenchmarkVersionCreateRequest(BaseModel):
    description: str | None = None
    question_set_id: uuid.UUID | None = None


class BenchmarkVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    question_set_id: uuid.UUID | None
    description: str | None
    metadata_json: dict | None
    created_by: uuid.UUID | None
    created_at: dt.datetime


class BenchmarkVersionListResponse(BaseModel):
    items: list[BenchmarkVersionResponse]
    total: int
    limit: int
    offset: int


class BenchmarkVersionCompareResponse(BaseModel):
    version1_id: uuid.UUID
    version2_id: uuid.UUID
    questions_added: int
    questions_removed: int
    questions_changed: int


class RollbackRequest(BaseModel):
    version_number: int
