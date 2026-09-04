"""Request/response bodies for api/routers/tool_config.py (Partie 5.1.4/5.1.5)."""

from pydantic import BaseModel


class ToolTimeoutResponse(BaseModel):
    tool_name: str
    timeout_seconds: float

    model_config = {"from_attributes": True}


class ToolTimeoutUpdateRequest(BaseModel):
    timeout_seconds: float


class ToolBudgetResponse(BaseModel):
    tool_name: str
    budget_limit: int
    tokens_used: int

    model_config = {"from_attributes": True}


class ToolBudgetUpdateRequest(BaseModel):
    budget_limit: int
