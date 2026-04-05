from __future__ import annotations

<<<<<<< HEAD
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
=======
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from rapidfuzz import fuzz
from sklearn.linear_model import LogisticRegression

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LAKE_DIR = DATA_DIR / "lake"
DB_PATH = DATA_DIR / "demo.db"
APP_VERSION = "0.1.0"
MODEL_VERSION = "mock-logreg-v1"
PIPELINE_VERSION = "pipeline-v1"

LAKE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Escopo 1 Demo - Conciliação Autônoma", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class Thresholds:
    auto_approve_ml: float = 0.50
    review_ml: float = 0.40
    fuzzy_similarity: float = 78.0
    materiality: float = 50000.0
    degradation_precision_floor: float = 0.90
    degradation_human_queue_ceiling: float = 0.40


THRESHOLDS = Thresholds()
ML_MODEL: Optional[LogisticRegression] = None


class ReviewPayload(BaseModel):
    action: str  # approve | reject
    selected_bank_tx_id: Optional[int] = None
    comment: str = ""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def date_diff_days(a: str, b: str) -> int:
    da = date.fromisoformat(a)
    db = date.fromisoformat(b)
    return abs((da - db).days)


def normalize_text(value: str) -> str:
    return " ".join((value or "").lower().replace("-", " ").replace("/", " ").split())


def text_similarity(a: str, b: str) -> float:
    return float(fuzz.token_sort_ratio(normalize_text(a), normalize_text(b)))


def amount_diff_ratio(a: float, b: float) -> float:
    if max(abs(a), abs(b)) == 0:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b))


def to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def create_schema() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS erp_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                tx_date TEXT NOT NULL,
                description TEXT NOT NULL,
                reference TEXT,
                account TEXT NOT NULL,
                expected_stage TEXT NOT NULL,
                expected_bank_external_id TEXT,
                processed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bank_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                tx_date TEXT NOT NULL,
                description TEXT NOT NULL,
                reference TEXT,
                account TEXT NOT NULL,
                matched INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                erp_tx_id INTEGER NOT NULL,
                bank_tx_id INTEGER,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT NOT NULL,
                human_required INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(erp_tx_id) REFERENCES erp_transactions(id),
                FOREIGN KEY(bank_tx_id) REFERENCES bank_transactions(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def log_event(conn: sqlite3.Connection, event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO events (event_type, entity_type, entity_id, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (event_type, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), now_iso()),
    )


def reset_demo_data() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(
            """
            DELETE FROM decisions;
            DELETE FROM events;
            DELETE FROM erp_transactions;
            DELETE FROM bank_transactions;
            DELETE FROM sqlite_sequence WHERE name IN ('decisions','events','erp_transactions','bank_transactions');
            """
        )
        conn.commit()
    seed_data(force=True)


def seed_data(force: bool = False) -> None:
    erp_seed = [
        ("ERP-001", 12500.00, "2026-04-01", "Pagamento NF 98765 - Fornecedor Alfa", "98765", "ITAU-001", "exact", "BNK-001"),
        ("ERP-002", 8900.00, "2026-04-01", "Pgto fornecedor Alfa Ltda", None, "ITAU-001", "fuzzy", "BNK-002"),
        ("ERP-003", 15000.00, "2026-04-02", "TED fornecedor Beta parcela abril", None, "ITAU-001", "ml", "BNK-003"),
        ("ERP-004", 78000.00, "2026-04-02", "Pagamento contrato Gama", None, "ITAU-001", "human", "BNK-004"),
        ("ERP-005", 4200.00, "2026-04-03", "Pagamento consultoria Zeta março", None, "ITAU-001", "human", None),
    ]

    bank_seed = [
        ("BNK-001", 12500.00, "2026-04-01", "PAGAMENTO NF 98765 FORN ALFA", "98765", "ITAU-001"),
        ("BNK-002", 8900.00, "2026-04-02", "PAG FORN ALFA LTDA", None, "ITAU-001"),
        ("BNK-003", 15000.00, "2026-04-04", "FORNECEDOR BETA ABRIL", None, "ITAU-001"),
        ("BNK-004", 78000.00, "2026-04-03", "PAGAMENTO CONTRATO GAMA", None, "ITAU-001"),
        ("BNK-005", 4200.00, "2026-04-03", "SERVICOS ZTX", None, "ITAU-001"),
        ("BNK-006", 4200.00, "2026-04-04", "TRANSFERENCIA ZETA HOLDING", None, "ITAU-001"),
    ]

    with closing(get_conn()) as conn:
        if not force:
            count = conn.execute("SELECT COUNT(*) AS c FROM erp_transactions").fetchone()["c"]
            if count:
                return

        conn.executemany(
            """
            INSERT INTO erp_transactions (external_id, amount, tx_date, description, reference, account, expected_stage, expected_bank_external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            erp_seed,
        )
        conn.executemany(
            """
            INSERT INTO bank_transactions (external_id, amount, tx_date, description, reference, account)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            bank_seed,
        )
        log_event(conn, "seed_completed", "system", "seed", {
            "erp_transactions": len(erp_seed),
            "bank_transactions": len(bank_seed),
            "pipeline_version": PIPELINE_VERSION,
            "model_version": MODEL_VERSION,
        })
        conn.commit()


def train_mock_model() -> LogisticRegression:
    X = np.array([
        [0.00, 0, 0.98, 1, 1],
        [0.00, 1, 0.79, 0, 1],
        [0.00, 2, 0.78, 0, 1],
        [0.01, 1, 0.70, 0, 1],
        [0.02, 2, 0.72, 0, 1],
        [0.00, 1, 0.90, 1, 1],
        [0.20, 0, 0.90, 0, 1],
        [0.00, 4, 0.50, 0, 1],
        [0.00, 2, 0.30, 0, 1],
        [0.05, 2, 0.45, 0, 1],
        [0.00, 1, 0.45, 0, 0],
        [0.00, 3, 0.35, 0, 1],
        [0.08, 1, 0.60, 0, 1],
        [0.00, 0, 0.40, 0, 1],
    ] * 5)
    y = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 5)

    model = LogisticRegression(max_iter=500, class_weight='balanced')
    model.fit(X, y)
    return model


def fetch_unprocessed_erp(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM erp_transactions WHERE processed = 0 ORDER BY id"
    ).fetchall()


def fetch_candidate_bank_rows(conn: sqlite3.Connection, erp_row: sqlite3.Row) -> List[sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM bank_transactions WHERE matched = 0 AND account = ? ORDER BY id",
        (erp_row["account"],),
    ).fetchall()
    candidates = []
    for row in rows:
        if date_diff_days(erp_row["tx_date"], row["tx_date"]) <= 3:
            candidates.append(row)
    return candidates


def exact_match(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]]]:
    scored = []
    matches = []
    for candidate in candidates:
        day_diff = date_diff_days(erp["tx_date"], candidate["tx_date"])
        ref_equal = bool(erp["reference"] and candidate["reference"] and erp["reference"] == candidate["reference"])
        amount_equal = math.isclose(erp["amount"], candidate["amount"], abs_tol=0.01)
        passed = amount_equal and ref_equal and day_diff <= 1
        entry = {
            "bank_tx_id": candidate["id"],
            "bank_external_id": candidate["external_id"],
            "amount_equal": amount_equal,
            "reference_equal": ref_equal,
            "day_diff": day_diff,
            "passed": passed,
        }
        scored.append(entry)
        if passed:
            matches.append(candidate)
    if len(matches) == 1:
        return matches[0], scored
    return None, scored


def fuzzy_match(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]]]:
    scored = []
    passed = []
    for candidate in candidates:
        similarity = text_similarity(erp["description"], candidate["description"])
        amount_equal = math.isclose(erp["amount"], candidate["amount"], abs_tol=0.01)
        day_diff = date_diff_days(erp["tx_date"], candidate["tx_date"])
        ok = amount_equal and similarity >= THRESHOLDS.fuzzy_similarity and day_diff <= 2
        entry = {
            "bank_tx_id": candidate["id"],
            "bank_external_id": candidate["external_id"],
            "similarity": similarity,
            "amount_equal": amount_equal,
            "day_diff": day_diff,
            "passed": ok,
        }
        scored.append(entry)
        if ok:
            passed.append((candidate, similarity))
    if len(passed) == 1:
        return passed[0][0], scored
    return None, scored


def ml_features(erp: sqlite3.Row, bank: sqlite3.Row) -> List[float]:
    return [
        amount_diff_ratio(erp["amount"], bank["amount"]),
        float(date_diff_days(erp["tx_date"], bank["tx_date"])),
        text_similarity(erp["description"], bank["description"]) / 100.0,
        1.0 if erp["reference"] and bank["reference"] and erp["reference"] == bank["reference"] else 0.0,
        1.0 if erp["account"] == bank["account"] else 0.0,
    ]


def ml_rank(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]], float]:
    if not candidates or ML_MODEL is None:
        return None, [], 0.0
    scores = []
    for candidate in candidates:
        features = ml_features(erp, candidate)
        probability = float(ML_MODEL.predict_proba([features])[0][1])
        scores.append(
            {
                "candidate": candidate,
                "probability": probability,
                "features": {
                    "amount_diff_ratio": round(features[0], 4),
                    "day_diff": int(features[1]),
                    "description_similarity": round(features[2] * 100, 2),
                    "reference_match": bool(features[3]),
                    "account_match": bool(features[4]),
                },
            }
        )
    scores.sort(key=lambda item: item["probability"], reverse=True)
    rendered = [
        {
            "bank_tx_id": item["candidate"]["id"],
            "bank_external_id": item["candidate"]["external_id"],
            "probability": round(item["probability"], 4),
            "features": item["features"],
        }
        for item in scores
    ]
    top = scores[0]
    return top["candidate"], rendered, top["probability"]


def create_decision(
    conn: sqlite3.Connection,
    erp_row: sqlite3.Row,
    bank_row: Optional[sqlite3.Row],
    stage: str,
    status: str,
    confidence: float,
    reasoning: str,
    human_required: bool,
) -> int:
    ts = now_iso()
    cur = conn.execute(
        """
        INSERT INTO decisions (erp_tx_id, bank_tx_id, stage, status, confidence, reasoning, human_required, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            erp_row["id"],
            bank_row["id"] if bank_row else None,
            stage,
            status,
            confidence,
            reasoning,
            1 if human_required else 0,
            ts,
            ts,
        ),
    )
    decision_id = int(cur.lastrowid)
    conn.execute("UPDATE erp_transactions SET processed = 1 WHERE id = ?", (erp_row["id"],))
    if bank_row and status in {"auto_approved", "human_approved"}:
        conn.execute("UPDATE bank_transactions SET matched = 1 WHERE id = ?", (bank_row["id"],))
    return decision_id


def export_lake_snapshot(conn: sqlite3.Connection) -> str:
    snapshot = {
        "exported_at": now_iso(),
        "app_version": APP_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "model_version": MODEL_VERSION,
        "decisions": [to_dict(row) for row in conn.execute("SELECT * FROM decisions ORDER BY id").fetchall()],
        "events": [
            {**to_dict(row), "payload_json": json.loads(row["payload_json"])}
            for row in conn.execute("SELECT * FROM events ORDER BY id").fetchall()
        ],
    }
    output_path = LAKE_DIR / f"snapshot-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path.relative_to(BASE_DIR))


def reconcile_once() -> Dict[str, Any]:
    with closing(get_conn()) as conn:
        batch_id = datetime.utcnow().strftime("BATCH-%Y%m%d%H%M%S")
        log_event(conn, "batch_started", "batch", batch_id, {
            "app_version": APP_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "model_version": MODEL_VERSION,
            "thresholds": THRESHOLDS.__dict__,
        })

        unprocessed = fetch_unprocessed_erp(conn)
        results = []

        for erp in unprocessed:
            entity_id = erp["external_id"]
            candidates = fetch_candidate_bank_rows(conn, erp)
            log_event(conn, "candidates_generated", "erp_transaction", entity_id, {
                "erp_transaction": to_dict(erp),
                "candidate_count": len(candidates),
                "candidate_external_ids": [row["external_id"] for row in candidates],
            })

            exact_candidate, exact_scores = exact_match(erp, candidates)
            log_event(conn, "exact_matching_evaluated", "erp_transaction", entity_id, {
                "scores": exact_scores,
            })
            if exact_candidate is not None:
                reason = "Match exato: valor e referência iguais, com diferença de data dentro da janela operacional."
                decision_id = create_decision(conn, erp, exact_candidate, "exact", "auto_approved", 0.99, reason, False)
                log_event(conn, "decision_created", "decision", str(decision_id), {
                    "erp_external_id": erp["external_id"],
                    "bank_external_id": exact_candidate["external_id"],
                    "stage": "exact",
                    "status": "auto_approved",
                    "confidence": 0.99,
                    "reasoning": reason,
                })
                results.append({"erp": erp["external_id"], "stage": "exact", "status": "auto_approved"})
                continue

            fuzzy_candidate, fuzzy_scores = fuzzy_match(erp, candidates)
            log_event(conn, "fuzzy_matching_evaluated", "erp_transaction", entity_id, {
                "scores": fuzzy_scores,
                "similarity_threshold": THRESHOLDS.fuzzy_similarity,
            })
            if fuzzy_candidate is not None:
                similarity = text_similarity(erp["description"], fuzzy_candidate["description"])
                if erp["amount"] >= THRESHOLDS.materiality:
                    reason = (
                        "Candidato fuzzy forte, mas o valor ultrapassa o limiar de materialidade; "
                        "a política exige revisão humana antes da aprovação."
                    )
                    decision_id = create_decision(conn, erp, fuzzy_candidate, "fuzzy", "human_review", similarity / 100.0, reason, True)
                    log_event(conn, "decision_created", "decision", str(decision_id), {
                        "erp_external_id": erp["external_id"],
                        "bank_external_id": fuzzy_candidate["external_id"],
                        "stage": "fuzzy",
                        "status": "human_review",
                        "confidence": round(similarity / 100.0, 4),
                        "reasoning": reason,
                        "reason": "materiality_threshold",
                    })
                    results.append({"erp": erp["external_id"], "stage": "fuzzy", "status": "human_review"})
                    continue
                reason = "Match fuzzy: valores iguais e histórico textual altamente semelhante dentro da janela de compensação."
                decision_id = create_decision(conn, erp, fuzzy_candidate, "fuzzy", "auto_approved", similarity / 100.0, reason, False)
                log_event(conn, "decision_created", "decision", str(decision_id), {
                    "erp_external_id": erp["external_id"],
                    "bank_external_id": fuzzy_candidate["external_id"],
                    "stage": "fuzzy",
                    "status": "auto_approved",
                    "confidence": round(similarity / 100.0, 4),
                    "reasoning": reason,
                })
                results.append({"erp": erp["external_id"], "stage": "fuzzy", "status": "auto_approved"})
                continue

            ml_candidate, ml_scores, ml_probability = ml_rank(erp, candidates)
            log_event(conn, "ml_matching_evaluated", "erp_transaction", entity_id, {
                "scores": ml_scores,
                "thresholds": {
                    "auto_approve_ml": THRESHOLDS.auto_approve_ml,
                    "review_ml": THRESHOLDS.review_ml,
                    "materiality": THRESHOLDS.materiality,
                },
            })
            if ml_candidate is not None and ml_probability >= THRESHOLDS.auto_approve_ml and erp["amount"] < THRESHOLDS.materiality:
                reason = (
                    "Match por ML: o modelo combinou proximidade de valor, datas, similaridade textual e conta. "
                    f"Probabilidade estimada: {ml_probability:.2%}."
                )
                decision_id = create_decision(conn, erp, ml_candidate, "ml", "auto_approved", ml_probability, reason, False)
                log_event(conn, "decision_created", "decision", str(decision_id), {
                    "erp_external_id": erp["external_id"],
                    "bank_external_id": ml_candidate["external_id"],
                    "stage": "ml",
                    "status": "auto_approved",
                    "confidence": round(ml_probability, 4),
                    "reasoning": reason,
                })
                results.append({"erp": erp["external_id"], "stage": "ml", "status": "auto_approved"})
                continue

            if ml_candidate is not None and ml_probability >= THRESHOLDS.review_ml:
                reason = (
                    "Candidato promissor, porém sem confiança suficiente para autoprovação ou sujeito a materialidade/ambiguidade. "
                    "O caso segue para revisão humana com sugestão de vínculo."
                )
                decision_id = create_decision(conn, erp, ml_candidate, "ml", "human_review", ml_probability, reason, True)
                log_event(conn, "decision_created", "decision", str(decision_id), {
                    "erp_external_id": erp["external_id"],
                    "bank_external_id": ml_candidate["external_id"],
                    "stage": "ml",
                    "status": "human_review",
                    "confidence": round(ml_probability, 4),
                    "reasoning": reason,
                })
                results.append({"erp": erp["external_id"], "stage": "ml", "status": "human_review"})
                continue

            reason = "Nenhuma regra ou score atingiu confiança suficiente; o caso foi direcionado para revisão humana."
            decision_id = create_decision(conn, erp, None, "human", "human_review", max(ml_probability, 0.0), reason, True)
            log_event(conn, "decision_created", "decision", str(decision_id), {
                "erp_external_id": erp["external_id"],
                "bank_external_id": None,
                "stage": "human",
                "status": "human_review",
                "confidence": round(max(ml_probability, 0.0), 4),
                "reasoning": reason,
            })
            results.append({"erp": erp["external_id"], "stage": "human", "status": "human_review"})

        lake_path = export_lake_snapshot(conn)
        log_event(conn, "batch_finished", "batch", batch_id, {
            "processed_transactions": len(unprocessed),
            "result_summary": results,
            "lake_snapshot": lake_path,
        })
        conn.commit()

    return {
        "batch_id": batch_id,
        "processed": len(results),
        "results": results,
        "lake_snapshot": lake_path,
    }


def get_decisions_with_context() -> List[Dict[str, Any]]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT d.*, e.external_id AS erp_external_id, e.amount AS erp_amount, e.description AS erp_description,
                   e.expected_stage, e.expected_bank_external_id,
                   b.external_id AS bank_external_id, b.description AS bank_description
            FROM decisions d
            JOIN erp_transactions e ON e.id = d.erp_tx_id
            LEFT JOIN bank_transactions b ON b.id = d.bank_tx_id
            ORDER BY d.id
            """
        ).fetchall()
        return [to_dict(row) for row in rows]


def compute_quality() -> Dict[str, Any]:
    decisions = get_decisions_with_context()
    total = len(decisions)
    if total == 0:
        return {
            "total_decisions": 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "human_queue_rate": None,
            "auto_approval_rate": None,
            "avg_confidence": None,
        }

    auto_decisions = [d for d in decisions if d["status"] == "auto_approved"]
    human_queue = [d for d in decisions if d["status"] == "human_review"]

    true_positive = 0
    false_positive = 0
    false_negative = 0
    correct_stage = 0

    for d in decisions:
        expected_bank = d["expected_bank_external_id"]
        got_bank = d["bank_external_id"]
        expected_stage = d["expected_stage"]
        got_stage = d["stage"]
        if expected_stage == got_stage:
            correct_stage += 1

        if expected_bank:
            if got_bank == expected_bank:
                true_positive += 1
            elif got_bank and got_bank != expected_bank:
                false_positive += 1
            elif got_bank is None:
                false_negative += 1
        else:
            if got_bank is not None:
                false_positive += 1

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    avg_confidence = sum(d["confidence"] for d in decisions) / total

    return {
        "total_decisions": total,
        "auto_approved": len(auto_decisions),
        "human_review": len(human_queue),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "human_queue_rate": round(len(human_queue) / total, 4),
        "auto_approval_rate": round(len(auto_decisions) / total, 4),
        "avg_confidence": round(avg_confidence, 4),
        "stage_accuracy": round(correct_stage / total, 4),
        "criteria": {
            "precision_goal": ">= 0.90",
            "human_queue_goal": "<= 0.40",
            "stage_accuracy_goal": ">= 0.80",
        },
    }


def compute_degradation() -> Dict[str, Any]:
    quality = compute_quality()
    if quality["total_decisions"] == 0:
        return {"status": "unknown", "reason": "No decisions yet."}

    issues = []
    if quality["precision"] is not None and quality["precision"] < THRESHOLDS.degradation_precision_floor:
        issues.append("precision_below_floor")
    if quality["human_queue_rate"] is not None and quality["human_queue_rate"] > THRESHOLDS.degradation_human_queue_ceiling:
        issues.append("human_queue_above_ceiling")

    status = "healthy" if not issues else "degraded"
    return {
        "status": status,
        "issues": issues,
        "baseline": {
            "precision_floor": THRESHOLDS.degradation_precision_floor,
            "human_queue_ceiling": THRESHOLDS.degradation_human_queue_ceiling,
        },
        "current": {
            "precision": quality.get("precision"),
            "human_queue_rate": quality.get("human_queue_rate"),
        },
        "recommended_action": (
            "Keep current autonomy." if status == "healthy" else
            "Reduce auto-approval, increase human sampling, and recalibrate thresholds."
        ),
    }
>>>>>>> dd27806656399473a21db3b282b330a5e55509ca


@app.on_event("startup")
def startup() -> None:
<<<<<<< HEAD
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
=======
    global ML_MODEL
    create_schema()
    seed_data()
    ML_MODEL = train_mock_model()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "app" / "static" / "index.html")


@app.post("/api/reset")
def api_reset() -> Dict[str, Any]:
    reset_demo_data()
    return {"message": "Demo resetada com sucesso."}


@app.post("/api/reconcile/run")
def api_reconcile_run() -> Dict[str, Any]:
    return reconcile_once()


@app.get("/api/transactions")
def api_transactions() -> Dict[str, Any]:
    with closing(get_conn()) as conn:
        erp = [to_dict(row) for row in conn.execute("SELECT * FROM erp_transactions ORDER BY id").fetchall()]
        bank = [to_dict(row) for row in conn.execute("SELECT * FROM bank_transactions ORDER BY id").fetchall()]
    return {"erp_transactions": erp, "bank_transactions": bank}


@app.get("/api/decisions")
def api_decisions() -> Dict[str, Any]:
    return {"decisions": get_decisions_with_context()}


@app.get("/api/events")
def api_events(limit: int = 100) -> Dict[str, Any]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        events = [{**to_dict(row), "payload_json": json.loads(row["payload_json"])} for row in rows]
    return {"events": events}


@app.get("/api/review/pending")
def api_review_pending() -> Dict[str, Any]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT d.*, e.external_id AS erp_external_id, e.description AS erp_description,
                   b.external_id AS bank_external_id, b.description AS bank_description
            FROM decisions d
            JOIN erp_transactions e ON e.id = d.erp_tx_id
            LEFT JOIN bank_transactions b ON b.id = d.bank_tx_id
            WHERE d.status = 'human_review'
            ORDER BY d.id
            """
        ).fetchall()
    return {"pending_review": [to_dict(row) for row in rows]}


@app.post("/api/review/{decision_id}")
def api_review_decision(decision_id: int, payload: ReviewPayload) -> Dict[str, Any]:
    if payload.action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Ação deve ser approve ou reject.")

    with closing(get_conn()) as conn:
        decision = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if not decision:
            raise HTTPException(status_code=404, detail="Decisão não encontrada.")
        if decision["status"] != "human_review":
            raise HTTPException(status_code=400, detail="Somente decisões pendentes podem ser revisadas.")

        bank_tx_id = decision["bank_tx_id"]
        if payload.action == "approve" and payload.selected_bank_tx_id:
            bank_tx_id = payload.selected_bank_tx_id
        ts = now_iso()
        status = "human_approved" if payload.action == "approve" else "human_rejected"
        reasoning = decision["reasoning"] + f" Revisão humana: {payload.comment or 'sem comentário'}"
        conn.execute(
            """
            UPDATE decisions
            SET status = ?, bank_tx_id = ?, reasoning = ?, updated_at = ?, human_required = 0
            WHERE id = ?
            """,
            (status, bank_tx_id, reasoning, ts, decision_id),
        )
        if payload.action == "approve" and bank_tx_id:
            conn.execute("UPDATE bank_transactions SET matched = 1 WHERE id = ?", (bank_tx_id,))
        log_event(conn, "human_review_completed", "decision", str(decision_id), {
            "action": payload.action,
            "selected_bank_tx_id": bank_tx_id,
            "comment": payload.comment,
        })
        conn.commit()

    return {"message": f"Decisão {decision_id} atualizada com {status}."}


@app.get("/api/quality")
def api_quality() -> Dict[str, Any]:
    return compute_quality()


@app.get("/api/degradation")
def api_degradation() -> Dict[str, Any]:
    return compute_degradation()


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app_version": APP_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "model_version": MODEL_VERSION,
        "database": str(DB_PATH),
    }
>>>>>>> dd27806656399473a21db3b282b330a5e55509ca
