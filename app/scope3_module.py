from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .escopo3_data import mock_roles, mock_transactions
from .escopo3_engine import Scope3Engine

router = APIRouter(prefix="/api/escopo3", tags=["Escopo 3"])
ENGINE = Scope3Engine()
LAST_RUN: dict | None = None


class SearchPayload(BaseModel):
    query: str
    role: str = "controller"


class AnalyzePayload(BaseModel):
    transaction_id: str
    role: str = "controller"


class FeedbackPayload(BaseModel):
    trace_id: str
    helpful: bool
    note: str = ""


@router.get("/dataset")
def dataset() -> dict:
    return {"roles": mock_roles(), "transactions": mock_transactions(), "documents": ENGINE.list_documents()}


@router.post("/search")
def search(payload: SearchPayload) -> dict:
    try:
        return ENGINE.search(payload.query, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/analyze")
def analyze(payload: AnalyzePayload) -> dict:
    global LAST_RUN
    try:
        LAST_RUN = ENGINE.analyze_transaction(payload.transaction_id, payload.role)
        return LAST_RUN
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/transactions")
def transactions() -> dict:
    return {"transactions": mock_transactions()}


@router.get("/documents")
def documents() -> dict:
    return {"documents": ENGINE.list_documents()}


@router.get("/traces")
def traces() -> dict:
    return {"traces": ENGINE.audit_traces, "feedback": ENGINE.feedback_log}


@router.get("/eval")
def evals() -> dict:
    return ENGINE.run_eval()


@router.post("/feedback")
def feedback(payload: FeedbackPayload) -> dict:
    return ENGINE.add_feedback(payload.trace_id, payload.helpful, payload.note)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "engine": "scope3_rag_demo", "roles": mock_roles()}
