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
from .scope1_module import router as scope1_router
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
    return templates.TemplateResponse("overview.html", {"request": request})


@app.get("/escopo1", response_class=HTMLResponse)
async def escopo1_page(request: Request) -> HTMLResponse:
    """Scope 1 reconciliation page."""
    return templates.TemplateResponse("escopo1.html", {"request": request})


@app.get("/escopo-1", response_class=HTMLResponse)
async def escopo1_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 1 page."""
    return await escopo1_page(request)


@app.get("/escopo2", response_class=HTMLResponse)
async def escopo2_page(request: Request) -> HTMLResponse:
    """Scope 2 anomaly detection page."""
    return templates.TemplateResponse("escopo2.html", {"request": request})


@app.get("/escopo-2", response_class=HTMLResponse)
async def escopo2_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 2 page."""
    return await escopo2_page(request)


@app.get("/escopo3", response_class=HTMLResponse)
async def escopo3_page(request: Request) -> HTMLResponse:
    """Scope 3 document analysis page."""
    return templates.TemplateResponse("escopo3.html", {"request": request})


@app.get("/escopo-3", response_class=HTMLResponse)
async def escopo3_alias(request: Request) -> HTMLResponse:
    """Legacy alias for Scope 3 page."""
    return await escopo3_page(request)


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request) -> HTMLResponse:
    """Audit and monitoring page."""
    return templates.TemplateResponse("audit.html", {"request": request})


# API routes for Scope 2
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


@app.post("/api/escopo3/analyze/{transaction_id}")
async def analyze_scope3_transaction(transaction_id: str, role: str = "controller") -> Dict[str, Any]:
    """Analyze Scope 3 transaction."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.analyze_transaction(transaction_id, role)


@app.get("/api/escopo3/search")
async def search_scope3_documents(query: str, role: str = "controller") -> Dict[str, Any]:
    """Search Scope 3 documents."""
    engine = ApplicationServices.get_scope3_engine()
    return engine.search_documents(query, role)


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
