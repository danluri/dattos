from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .escopo2_data import TransactionRepository as Escopo2DataRepo
from .escopo2_engine import AnomalyDetectionEngine
from .escopo3_data import DocumentDataRepository
from .escopo3_engine import Scope3ProcessingEngine
from .scope1_module import EventQueryService, QualityAnalyzer, TransactionQueryService, router as scope1_router
from .scope3_module import router as scope3_router

# Application configuration
APP_TITLE = "Dattos Demo Unificada — Escopos 1, 2 e 3"
APP_VERSION = "3.0.0"
APP_DESCRIPTION = "Unified application with functionalities for Scopes 1, 2 and 3 demos, including a more complete RAG module for Scope 3."

# Initialize FastAPI application
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)

# Setup static files and templates
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API routers
app.include_router(scope1_router)
app.include_router(scope3_router)

# Global state for demo data
SCOPE2_LAST_RESULT: Dict[str, Any] | None = None
SCOPE3_LAST_BATCH: list[Dict[str, Any]] = []


class ApplicationServices:
    """Centralized application services."""

    @staticmethod
    def initialize_modules() -> None:
        """Initialize all application modules."""
        # Initialize Scope 1 module
        from .scope1_module import initialize_scope1_module
        initialize_scope1_module()

    @staticmethod
    def get_scope2_engine() -> AnomalyDetectionEngine:
        """Get initialized Scope 2 engine."""
        return AnomalyDetectionEngine()

    @staticmethod
    def get_scope3_engine() -> Scope3ProcessingEngine:
        """Get initialized Scope 3 engine."""
        return Scope3ProcessingEngine()


# Initialize modules on startup
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    ApplicationServices.initialize_modules()


# Web routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    return templates.TemplateResponse("overview.html", {"request": request, "page": "overview"})


@app.get("/escopo1", response_class=HTMLResponse)
async def escopo1_page(request: Request) -> HTMLResponse:
    """Scope 1 reconciliation page."""
    counts = TransactionQueryService.get_all_transactions()
    pending = TransactionQueryService.get_pending_human_reviews()
    return templates.TemplateResponse("escopo1.html", {
        "request": request,
        "page": "escopo1",
        "totvs_count": len(counts["erp_transactions"]),
        "bank_count": len(counts["bank_transactions"]),
        "pending_count": len(pending),
    })


@app.get("/escopo-1", response_class=HTMLResponse)
async def escopo1_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 1 page."""
    return await escopo1_page(request)


@app.get("/escopo2", response_class=HTMLResponse)
async def escopo2_page(request: Request) -> HTMLResponse:
    """Scope 2 anomaly detection page."""
    history = Escopo2DataRepo.get_historical_transactions()
    current = Escopo2DataRepo.get_current_transaction_batch()
    return templates.TemplateResponse("escopo2.html", {
        "request": request,
        "page": "escopo2",
        "history_count": len(history),
        "current_count": len(current)
    })


@app.get("/escopo-2", response_class=HTMLResponse)
async def escopo2_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 2 page."""
    return await escopo2_page(request)


@app.get("/escopo3", response_class=HTMLResponse)
async def escopo3_page(request: Request) -> HTMLResponse:
    """Scope 3 document analysis page."""
    repo = DocumentDataRepository()
    return templates.TemplateResponse("escopo3.html", {
        "request": request,
        "page": "escopo3",
        "doc_count": len(repo.get_document_chunks()),
        "tx_count": len(repo.get_transaction_records())
    })


@app.get("/escopo-3", response_class=HTMLResponse)
async def escopo3_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 3 page."""
    return await escopo3_page(request)


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request) -> HTMLResponse:
    """Audit and monitoring page."""
    return templates.TemplateResponse("audit.html", {"request": request, "page": "audit"})


@app.get("/api/audit/combined")
async def get_combined_audit() -> Dict[str, Any]:
    """Get combined audit metrics for all scopes."""
    scope1_metrics = QualityAnalyzer.compute_quality_metrics()
    scope2_metrics = SCOPE2_LAST_RESULT.get("metrics") if isinstance(SCOPE2_LAST_RESULT, dict) else None
    if scope2_metrics is None:
        scope2_metrics = {"precision_at_k": 0.0, "recall": 0.0, "inconclusive_rate": 0.0}

    scope3_metrics = ApplicationServices.get_scope3_engine().run_evaluation()["metrics"]
    events = EventQueryService.get_recent_events(limit=50)
    audit_events = [
        {
            "scope": "Escopo 1",
            "event_type": event.get("event_type"),
            "entity_id": event.get("entity_id"),
            "trace_id": event.get("id"),
            "resolution": event.get("payload_json", {}).get("result") if isinstance(event.get("payload_json"), dict) else None,
            "status": event.get("payload_json", {}).get("status") if isinstance(event.get("payload_json"), dict) else None,
            **event
        }
        for event in events
    ]

    return {
        "summary": {
            "escopo1": {
                "precision": scope1_metrics.get("precision"),
                "human_queue_rate": scope1_metrics.get("human_queue_rate"),
                "f1": scope1_metrics.get("f1")
            },
            "escopo2": {
                "precision_at_k": scope2_metrics.get("precision_at_k"),
                "recall": scope2_metrics.get("recall"),
                "inconclusive_rate": scope2_metrics.get("inconclusive_rate")
            },
            "escopo3": {
                "ndcg_at_10": scope3_metrics.get("ndcg_at_10"),
                "recall_at_5": scope3_metrics.get("recall_at_5"),
                "faithfulness": scope3_metrics.get("faithfulness")
            },
            "counts": {
                "total_events": len(audit_events),
                "scope1_events": len(audit_events),
                "scope2_events": 0,
                "scope3_events": 0
            }
        },
        "audit_events": audit_events
    }


# API routes for Scope 2
@app.get("/api/escopo2/dataset")
async def get_scope2_dataset() -> Dict[str, Any]:
    """Get Scope 2 dataset (history and current batch)."""
    from .escopo2_data import mock_history, mock_current_batch
    return {
        "history": mock_history(),
        "current_batch": mock_current_batch()
    }


@app.get("/api/escopo2/transactions")
async def get_scope2_transactions() -> Dict[str, Any]:
    """Get Scope 2 transaction data."""
    repo = Escopo2DataRepo()
    return {
        "historical": repo.get_historical_transactions(),
        "current_batch": repo.get_current_transaction_batch()
    }


@app.post("/api/escopo2/run")
async def run_scope2_analysis() -> Dict[str, Any]:
    """Run Scope 2 anomaly detection."""
    global SCOPE2_LAST_RESULT
    engine = ApplicationServices.get_scope2_engine()
    SCOPE2_LAST_RESULT = engine.run_detection()
    return SCOPE2_LAST_RESULT


@app.get("/api/escopo2/last-result")
async def get_scope2_last_result() -> Dict[str, Any]:
    """Get last Scope 2 analysis result."""
    if SCOPE2_LAST_RESULT is None:
        return {"error": "No analysis run yet"}
    return SCOPE2_LAST_RESULT


# API routes for Scope 3
@app.get("/api/escopo3/dataset")
async def get_scope3_dataset() -> Dict[str, Any]:
    """Get Scope 3 dataset (transactions, documents, roles)."""
    from .escopo3_data import mock_transactions, mock_chunks, mock_roles
    return {
        "transactions": mock_transactions(),
        "documents": mock_chunks(),
        "roles": mock_roles()
    }


@app.get("/api/escopo3/documents")
async def get_scope3_documents() -> Dict[str, Any]:
    """Get Scope 3 document data."""
    repo = DocumentDataRepository()
    return {"documents": repo.get_all_documents()}


@app.get("/api/escopo3/transactions")
async def get_scope3_transactions() -> Dict[str, Any]:
    """Get Scope 3 transaction data."""
    repo = DocumentDataRepository()
    return {"transactions": repo.get_all_transactions()}


@app.post("/api/escopo3/analyze")
async def analyze_scope3_transaction_post(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Scope 3 transaction (POST with body)."""
    transaction_id = data.get("transaction_id", "TX-1001")
    role = data.get("role", "controller")
    engine = ApplicationServices.get_scope3_engine()
    return engine.analyze_transaction(transaction_id, role)


@app.post("/api/escopo3/analyze/{transaction_id}")
async def analyze_scope3_transaction(transaction_id: str, role: str = "controller") -> Dict[str, Any]:
    """Analyze Scope 3 transaction (URL-based)."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.analyze_transaction(transaction_id, role)


@app.post("/api/escopo3/search")
async def search_scope3_documents_post(data: Dict[str, Any]) -> Dict[str, Any]:
    """Search Scope 3 documents (POST with body)."""
    query = data.get("query", "")
    role = data.get("role", "controller")
    engine = ApplicationServices.get_scope3_engine()
    return engine.search_documents(query, role)


@app.get("/api/escopo3/search")
async def search_scope3_documents(query: str, role: str = "controller") -> Dict[str, Any]:
    """Search Scope 3 documents (GET)."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.search_documents(query, role)


@app.get("/api/escopo3/eval")
async def evaluate_scope3_get() -> Dict[str, Any]:
    """Run Scope 3 system evaluation (GET)."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.run_evaluation()


@app.post("/api/escopo3/evaluate")
async def evaluate_scope3_system() -> Dict[str, Any]:
    """Run Scope 3 system evaluation."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.run_evaluation()


# Health check
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Application health check."""
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "modules": {
            "scope1": "initialized",
            "scope2": "available",
            "scope3": "available"
        }
    }


@app.get("/api/health")
async def api_health_check() -> Dict[str, Any]:
    """Legacy API health check endpoint for compatibility."""
    return await health_check()


# Backward compatibility routes
@app.get("/api/transactions")
async def legacy_get_transactions() -> Dict[str, Any]:
    """Legacy endpoint for transactions."""
    return await get_scope2_transactions()


@app.post("/api/run")
async def legacy_run_analysis() -> Dict[str, Any]:
    """Legacy endpoint for analysis."""
    return await run_scope2_analysis()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
