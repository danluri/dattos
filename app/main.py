from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .escopo2_data import mock_current_batch, mock_history
from .escopo2_engine import DetectorEngine
from .scope1_module import (
    ReviewPayload,
    api_decisions,
    api_degradation,
    api_events,
    api_quality,
    api_reconcile_run,
    api_reset,
    api_review_decision,
    api_review_pending,
    api_transactions,
    get_events as get_scope1_events,
    get_pending_review,
    get_transactions as get_scope1_transactions,
    init_scope1,
    router as scope1_router,
)
from .scope3_module import ENGINE as SCOPE3_ENGINE
from .scope3_module import router as scope3_router

app = FastAPI(
    title="Dattos Demo Unificada — Escopos 1, 2 e 3",
    version="3.0.0",
    description="Aplicação única com as funcionalidades dos demos e um módulo RAG mais completo para o Escopo 3.",
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(scope1_router)
app.include_router(scope3_router)

LAST_SCOPE2: dict | None = None
LAST_SCOPE3_BATCH: list[dict] = []


@app.on_event("startup")
def startup() -> None:
    init_scope1()


@app.get("/", response_class=HTMLResponse)
def overview(request: Request) -> HTMLResponse:
    txs = get_scope1_transactions()
    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "page": "overview",
            "scope1_erp_count": len(txs["erp_transactions"]),
            "scope1_bank_count": len(txs["bank_transactions"]),
            "history_count": len(mock_history()),
            "current_count": len(mock_current_batch()),
            "scope3_docs": len(SCOPE3_ENGINE.list_documents()),
            "scope3_txs": len(SCOPE3_ENGINE.transactions),
        },
    )


@app.get("/escopo-1", response_class=HTMLResponse)
def escopo1_page(request: Request) -> HTMLResponse:
    txs = get_scope1_transactions()
    return templates.TemplateResponse(request, "escopo1.html", {"page": "escopo1", "totvs_count": len(txs["erp_transactions"]), "bank_count": len(txs["bank_transactions"]), "pending_count": len(get_pending_review())})


@app.get("/escopo-2", response_class=HTMLResponse)
def escopo2_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "escopo2.html", {"page": "escopo2", "history_count": len(mock_history()), "current_count": len(mock_current_batch())})


@app.get("/escopo-3", response_class=HTMLResponse)
def escopo3_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "escopo3.html", {"page": "escopo3", "doc_count": len(SCOPE3_ENGINE.list_documents()), "tx_count": len(SCOPE3_ENGINE.transactions)})


@app.get("/auditoria", response_class=HTMLResponse)
def audit_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "audit.html", {"page": "audit"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/escopo2/dataset", tags=["Escopo 2"])
def escopo2_dataset() -> dict:
    return {"history": mock_history(), "current_batch": [{k: v for k, v in row.items() if k != "expected_label"} for row in mock_current_batch()]}


@app.post("/api/escopo2/run", tags=["Escopo 2"])
def run_scope2() -> JSONResponse:
    global LAST_SCOPE2
    LAST_SCOPE2 = DetectorEngine().run()
    return JSONResponse(LAST_SCOPE2)


@app.get("/api/escopo2/results", tags=["Escopo 2"])
def escopo2_results() -> JSONResponse:
    global LAST_SCOPE2
    if LAST_SCOPE2 is None:
        LAST_SCOPE2 = DetectorEngine().run()
    return JSONResponse(LAST_SCOPE2)


@app.get("/api/escopo2/health", tags=["Escopo 2"])
def escopo2_health() -> dict:
    return {"status": "ok", "engine": "detector_engine_v1"}


@app.post("/api/run-all", tags=["Plataforma"])
def run_all() -> JSONResponse:
    global LAST_SCOPE2, LAST_SCOPE3_BATCH
    api_reset()
    scope1 = api_reconcile_run()
    LAST_SCOPE2 = DetectorEngine().run()
    LAST_SCOPE3_BATCH = [
        SCOPE3_ENGINE.analyze_transaction("TX-1001", "controller"),
        SCOPE3_ENGINE.analyze_transaction("TX-1003", "controller"),
        SCOPE3_ENGINE.analyze_transaction("TX-1004", "auditor_externo"),
    ]
    return JSONResponse({"escopo1": scope1, "escopo2": LAST_SCOPE2, "escopo3": LAST_SCOPE3_BATCH})


@app.get("/api/audit/combined", tags=["Plataforma"])
def combined_audit() -> JSONResponse:
    global LAST_SCOPE2
    if LAST_SCOPE2 is None:
        LAST_SCOPE2 = DetectorEngine().run()
    scope1_events = get_scope1_events(50)
    audit_events = []
    audit_events.extend({**event, "scope": "Escopo 1"} for event in scope1_events)
    audit_events.extend({**event, "scope": "Escopo 2"} for event in LAST_SCOPE2["audit_events"])
    audit_events.extend({**trace, "scope": "Escopo 3"} for trace in SCOPE3_ENGINE.audit_traces[-20:])
    summary = {
        "escopo1": api_quality(),
        "escopo2": LAST_SCOPE2["metrics"],
        "escopo3": SCOPE3_ENGINE.run_eval()["metrics"],
        "counts": {"total_events": len(audit_events), "scope1_events": len(scope1_events), "scope2_events": len(LAST_SCOPE2["audit_events"]), "scope3_events": len(SCOPE3_ENGINE.audit_traces[-20:])},
    }
    return JSONResponse({"audit_events": audit_events, "summary": summary})


# Compatibilidade com o demo individual do Escopo 1
@app.post("/api/reset", tags=["Compatibilidade Escopo 1"])
def compat_reset() -> dict:
    return api_reset()


@app.post("/api/reconcile/run", tags=["Compatibilidade Escopo 1"])
def compat_run() -> dict:
    return api_reconcile_run()


@app.get("/api/transactions", tags=["Compatibilidade Escopo 1"])
def compat_transactions() -> dict:
    return api_transactions()


@app.get("/api/decisions", tags=["Compatibilidade Escopo 1"])
def compat_decisions() -> dict:
    return api_decisions()


@app.get("/api/events", tags=["Compatibilidade Escopo 1"])
def compat_events(limit: int = 100) -> dict:
    return api_events(limit)


@app.get("/api/review/pending", tags=["Compatibilidade Escopo 1"])
def compat_review_pending() -> dict:
    return api_review_pending()


@app.post("/api/review/{decision_id}", tags=["Compatibilidade Escopo 1"])
def compat_review_decision(decision_id: int, payload: ReviewPayload) -> dict:
    return api_review_decision(decision_id, payload)


@app.get("/api/quality", tags=["Compatibilidade Escopo 1"])
def compat_quality() -> dict:
    return api_quality()


@app.get("/api/degradation", tags=["Compatibilidade Escopo 1"])
def compat_degradation() -> dict:
    return api_degradation()
