"""Navigator router; include this router in the backend's FastAPI application."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import llm, navigator
from .budget import BudgetError

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    storm_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")


class AskResponse(BaseModel):
    answer: str
    verified: bool
    unverified_numbers: list[str]
    tool_calls: list[dict[str, Any]]
    inspector: dict[str, Any]
    scenario: dict[str, Any] | None


@router.post("/api/navigator/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    # A synchronous handler runs in FastAPI's threadpool; provider I/O never
    # blocks its async event loop. Live mode is configured on the server only.
    try:
        return navigator.ask(request.question, storm_id=request.storm_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except BudgetError:
        raise HTTPException(status_code=503, detail="Navigator model budget is unavailable") from None
    except llm.GatewayError:
        raise HTTPException(status_code=502, detail="Navigator model provider is unavailable") from None
