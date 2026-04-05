from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .escopo3_data import DocumentDataRepository
from .escopo3_engine import Scope3ProcessingEngine

# API router
router = APIRouter(prefix="/api/escopo3", tags=["Escopo 3"])

# Global engine instance
ENGINE = Scope3ProcessingEngine()
LAST_ANALYSIS_RESULT: Dict[str, Any] | None = None


class SearchRequest(BaseModel):
    """Request payload for document search."""
    query: str
    role: str = "controller"


class AnalysisRequest(BaseModel):
    """Request payload for transaction analysis."""
    transaction_id: str
    role: str = "controller"


class FeedbackRequest(BaseModel):
    """Request payload for user feedback."""
    trace_id: str
    helpful: bool
    note: str = ""


class Scope3APIService:
    """Service for Scope 3 API operations."""

    @staticmethod
    def get_dataset() -> Dict[str, Any]:
        """Get complete dataset for Scope 3."""
        repo = DocumentDataRepository()

        return {
            "roles": repo.get_user_roles(),
            "transactions": repo.get_transaction_records(),
            "documents": ENGINE.list_documents()
        }

    @staticmethod
    def search_documents(query: str, role: str) -> Dict[str, Any]:
        """Search documents using the processing engine."""
        if role not in ENGINE.roles:
            raise ValueError("Invalid profile")

        return ENGINE.search_documents(query, role)

    @staticmethod
    def analyze_transaction(transaction_id: str, role: str) -> Dict[str, Any]:
        """Analyze transaction using the processing engine."""
        global LAST_ANALYSIS_RESULT

        if role not in ENGINE.roles:
            raise ValueError("Invalid profile")

        # Verify transaction exists
        try:
            ENGINE.find_transaction(transaction_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

        result = ENGINE.analyze_transaction(transaction_id, role)
        LAST_ANALYSIS_RESULT = result
        return result

    @staticmethod
    def get_transactions() -> Dict[str, Any]:
        """Get all transactions."""
        repo = DocumentDataRepository()
        return {"transactions": repo.get_transaction_records()}

    @staticmethod
    def get_documents() -> Dict[str, Any]:
        """Get all documents."""
        return {"documents": ENGINE.list_documents()}

    @staticmethod
    def get_audit_data() -> Dict[str, Any]:
        """Get audit traces and feedback."""
        return {
            "traces": ENGINE.audit_traces,
            "feedback": ENGINE.feedback_manager.get_feedback_log()
        }

    @staticmethod
    def run_evaluation() -> Dict[str, Any]:
        """Run system evaluation."""
        return ENGINE.run_evaluation()

    @staticmethod
    def add_user_feedback(trace_id: str, helpful: bool, note: str) -> Dict[str, Any]:
        """Add user feedback."""
        return ENGINE.add_feedback(trace_id, helpful, note)

    @staticmethod
    def get_health_status() -> Dict[str, Any]:
        """Get system health status."""
        role_repo = RoleRepository()
        return {
            "status": "ok",
            "engine": "scope3_rag_demo",
            "roles": role_repo.get_all_roles()
        }


# API Endpoints
@router.get("/dataset")
def get_dataset_endpoint() -> Dict[str, Any]:
    """Get complete dataset for Scope 3 demo."""
    return Scope3APIService.get_dataset()


@router.post("/search")
def search_documents_endpoint(payload: SearchRequest) -> Dict[str, Any]:
    """Search documents by query."""
    try:
        return Scope3APIService.search_documents(payload.query, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/analyze")
def analyze_transaction_endpoint(payload: AnalysisRequest) -> Dict[str, Any]:
    """Analyze transaction with document retrieval."""
    return Scope3APIService.analyze_transaction(payload.transaction_id, payload.role)


@router.get("/transactions")
def get_transactions_endpoint() -> Dict[str, Any]:
    """Get all transactions."""
    return Scope3APIService.get_transactions()


@router.get("/documents")
def get_documents_endpoint() -> Dict[str, Any]:
    """Get all documents."""
    return Scope3APIService.get_documents()


@router.get("/traces")
def get_audit_traces_endpoint() -> Dict[str, Any]:
    """Get audit traces and feedback log."""
    return Scope3APIService.get_audit_data()


@router.get("/eval")
def run_evaluation_endpoint() -> Dict[str, Any]:
    """Run system evaluation."""
    return Scope3APIService.run_evaluation()


@router.post("/feedback")
def add_feedback_endpoint(payload: FeedbackRequest) -> Dict[str, Any]:
    """Add user feedback on analysis results."""
    return Scope3APIService.add_user_feedback(payload.trace_id, payload.helpful, payload.note)


@router.get("/health")
def get_health_endpoint() -> Dict[str, Any]:
    """Get system health status."""
    return Scope3APIService.get_health_status()


@router.get("/last-analysis")
def get_last_analysis_endpoint() -> Dict[str, Any]:
    """Get last analysis result."""
    if LAST_ANALYSIS_RESULT is None:
        return {"error": "No analysis run yet"}
    return LAST_ANALYSIS_RESULT


# Backward compatibility endpoints
@router.get("/status")
def get_status_endpoint() -> Dict[str, Any]:
    """Legacy status endpoint."""
    return Scope3APIService.get_health_status()
