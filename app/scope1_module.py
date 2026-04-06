from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rapidfuzz import fuzz
from sklearn.linear_model import LogisticRegression

# System constants
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LAKE_DIR = DATA_DIR / "lake"
DB_PATH = DATA_DIR / "scope1_demo.db"
APP_VERSION = "1.0.0"
MODEL_VERSION = "mock-logreg-v1"
PIPELINE_VERSION = "pipeline-v1"

# Ensure directories exist
LAKE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API router
router = APIRouter(prefix="/api/escopo1", tags=["Escopo 1"])


@dataclass
class ReconciliationThresholds:
    """Configuration thresholds for reconciliation pipeline."""
    auto_approve_ml: float = 0.50
    review_ml: float = 0.40
    fuzzy_similarity: float = 78.0
    materiality: float = 50000.0
    degradation_precision_floor: float = 0.90
    degradation_human_queue_ceiling: float = 0.40


@dataclass
class ERPTransactionData:
    """ERP transaction record."""
    external_id: str
    amount: float
    tx_date: str
    description: str
    reference: Optional[str]
    account: str
    expected_stage: str
    expected_bank_external_id: Optional[str]


@dataclass
class BankTransactionData:
    """Bank transaction record."""
    external_id: str
    amount: float
    tx_date: str
    description: str
    reference: Optional[str]
    account: str


# Global configuration
RECONCILIATION_THRESHOLDS = ReconciliationThresholds()
ML_MODEL_INSTANCE: Optional[LogisticRegression] = None


class ReviewDecisionPayload(BaseModel):
    """Payload for reviewing reconciliation decisions."""
    action: str  # approve | reject
    selected_bank_tx_id: Optional[int] = None
    comment: str = ""


class HumanReviewAction(BaseModel):
    """Payload for human review actions."""
    erp_id: str
    action: str  # confirm_match | approve | reject
    reviewer: str = "controller.demo"
    note: str = ""
    selected_bank_tx_id: Optional[int] = None


class DatabaseService:
    """Service for database operations."""

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def get_current_timestamp() -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    @staticmethod
    def calculate_date_difference(a: str, b: str) -> int:
        """Calculate absolute difference in days between two dates."""
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)

    @staticmethod
    def normalize_text_input(value: str) -> str:
        """Normalize text for comparison."""
        return " ".join((value or "").lower().replace("-", " ").replace("/", " ").split())

    @staticmethod
    def calculate_text_similarity(a: str, b: str) -> float:
        """Calculate text similarity using fuzzy matching."""
        return float(fuzz.token_sort_ratio(DatabaseService.normalize_text_input(a), DatabaseService.normalize_text_input(b)))

    @staticmethod
    def calculate_amount_difference_ratio(a: float, b: float) -> float:
        """Calculate relative difference between amounts."""
        if max(abs(a), abs(b)) == 0:
            return 0.0
        return abs(a - b) / max(abs(a), abs(b))

    @staticmethod
    def convert_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to dictionary."""
        return {k: row[k] for k in row.keys()}


class SchemaManager:
    """Manages database schema creation."""

    @staticmethod
    def create_database_schema() -> None:
        """Create all required database tables."""
        with closing(DatabaseService.get_connection()) as conn:
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


class EventLogger:
    """Handles event logging to database."""

    @staticmethod
    def log_event(conn: sqlite3.Connection, event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]) -> None:
        """Log an event to the database."""
        conn.execute(
            "INSERT INTO events (event_type, entity_type, entity_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_type, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), DatabaseService.get_current_timestamp()),
        )


class DataSeeder:
    """Handles seeding of demo data."""

    # ERP transaction seed data
    ERP_SEED_DATA = [
        ERPTransactionData(
            external_id="ERP-001",
            amount=12500.00,
            tx_date="2026-04-01",
            description="Pagamento NF 98765 - Fornecedor Alfa",
            reference="98765",
            account="ITAU-001",
            expected_stage="exact",
            expected_bank_external_id="BNK-001",
        ),
        ERPTransactionData(
            external_id="ERP-002",
            amount=8900.00,
            tx_date="2026-04-01",
            description="Pgto fornecedor Alfa Ltda",
            reference=None,
            account="ITAU-001",
            expected_stage="fuzzy",
            expected_bank_external_id="BNK-002",
        ),
        ERPTransactionData(
            external_id="ERP-003",
            amount=15000.00,
            tx_date="2026-04-02",
            description="TED fornecedor Beta parcela abril",
            reference=None,
            account="ITAU-001",
            expected_stage="ml",
            expected_bank_external_id="BNK-003",
        ),
        ERPTransactionData(
            external_id="ERP-004",
            amount=78000.00,
            tx_date="2026-04-02",
            description="Pagamento contrato Gama",
            reference=None,
            account="ITAU-001",
            expected_stage="human",
            expected_bank_external_id="BNK-004",
        ),
        ERPTransactionData(
            external_id="ERP-005",
            amount=4200.00,
            tx_date="2026-04-03",
            description="Pagamento consultoria Zeta março",
            reference=None,
            account="ITAU-001",
            expected_stage="human",
            expected_bank_external_id=None,
        ),
    ]

    # Bank transaction seed data
    BANK_SEED_DATA = [
        BankTransactionData(
            external_id="BNK-001",
            amount=12500.00,
            tx_date="2026-04-01",
            description="PAGAMENTO NF 98765 FORN ALFA",
            reference="98765",
            account="ITAU-001",
        ),
        BankTransactionData(
            external_id="BNK-002",
            amount=8900.00,
            tx_date="2026-04-02",
            description="PAG FORN ALFA LTDA",
            reference=None,
            account="ITAU-001",
        ),
        BankTransactionData(
            external_id="BNK-003",
            amount=15000.00,
            tx_date="2026-04-04",
            description="FORNECEDOR BETA ABRIL",
            reference=None,
            account="ITAU-001",
        ),
        BankTransactionData(
            external_id="BNK-004",
            amount=78000.00,
            tx_date="2026-04-03",
            description="PAGAMENTO CONTRATO GAMA",
            reference=None,
            account="ITAU-001",
        ),
        BankTransactionData(
            external_id="BNK-005",
            amount=4200.00,
            tx_date="2026-04-03",
            description="SERVICOS ZTX",
            reference=None,
            account="ITAU-001",
        ),
        BankTransactionData(
            external_id="BNK-006",
            amount=4200.00,
            tx_date="2026-04-04",
            description="TRANSFERENCIA ZETA HOLDING",
            reference=None,
            account="ITAU-001",
        ),
    ]

    @staticmethod
    def reset_demo_data() -> None:
        """Reset all demo data."""
        with closing(DatabaseService.get_connection()) as conn:
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

    @staticmethod
    def seed_demo_data(force: bool = False) -> None:
        """Seed demo data if not already present."""
        with closing(DatabaseService.get_connection()) as conn:
            if not force:
                count = conn.execute("SELECT COUNT(*) AS c FROM erp_transactions").fetchone()["c"]
                if count:
                    return

            # Insert ERP transactions
            conn.executemany(
                "INSERT INTO erp_transactions (external_id, amount, tx_date, description, reference, account, expected_stage, expected_bank_external_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(data.external_id, data.amount, data.tx_date, data.description, data.reference, data.account, data.expected_stage, data.expected_bank_external_id) for data in DataSeeder.ERP_SEED_DATA],
            )

            # Insert bank transactions
            conn.executemany(
                "INSERT INTO bank_transactions (external_id, amount, tx_date, description, reference, account) VALUES (?, ?, ?, ?, ?, ?)",
                [(data.external_id, data.amount, data.tx_date, data.description, data.reference, data.account) for data in DataSeeder.BANK_SEED_DATA],
            )

            # Log seeding event
            EventLogger.log_event(conn, "seed_completed", "system", "seed", {
                "erp_transactions": len(DataSeeder.ERP_SEED_DATA),
                "bank_transactions": len(DataSeeder.BANK_SEED_DATA),
                "pipeline_version": PIPELINE_VERSION,
                "model_version": MODEL_VERSION
            })
            conn.commit()


class MLModelTrainer:
    """Handles ML model training and management."""

    # Training data features and labels
    TRAINING_FEATURES = np.array([
        [0.00, 0, 0.98, 1, 1], [0.00, 1, 0.79, 0, 1], [0.00, 2, 0.78, 0, 1], [0.01, 1, 0.70, 0, 1],
        [0.02, 2, 0.72, 0, 1], [0.00, 1, 0.90, 1, 1], [0.20, 0, 0.90, 0, 1], [0.00, 4, 0.50, 0, 1],
        [0.00, 2, 0.30, 0, 1], [0.05, 2, 0.45, 0, 1], [0.00, 1, 0.45, 0, 0], [0.00, 3, 0.35, 0, 1],
        [0.08, 1, 0.60, 0, 1], [0.00, 0, 0.40, 0, 1],
    ] * 5)

    TRAINING_LABELS = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 5)

    @staticmethod
    def train_model() -> LogisticRegression:
        """Train and return the ML model."""
        model = LogisticRegression(max_iter=500, class_weight="balanced")
        model.fit(MLModelTrainer.TRAINING_FEATURES, MLModelTrainer.TRAINING_LABELS)
        return model


class TransactionMatcher:
    """Handles transaction matching logic."""

    @staticmethod
    def get_unprocessed_erp_transactions(conn: sqlite3.Connection) -> List[sqlite3.Row]:
        """Retrieve unprocessed ERP transactions."""
        return conn.execute("SELECT * FROM erp_transactions WHERE processed = 0 ORDER BY id").fetchall()

    @staticmethod
    def get_candidate_bank_transactions(conn: sqlite3.Connection, erp_row: sqlite3.Row) -> List[sqlite3.Row]:
        """Get candidate bank transactions for matching."""
        rows = conn.execute("SELECT * FROM bank_transactions WHERE matched = 0 AND account = ? ORDER BY id", (erp_row["account"],)).fetchall()
        return [row for row in rows if DatabaseService.calculate_date_difference(erp_row["tx_date"], row["tx_date"]) <= 3]

    @staticmethod
    def perform_exact_matching(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]]]:
        """Perform exact matching between ERP and bank transactions."""
        scored, matches = [], []
        for candidate in candidates:
            day_diff = DatabaseService.calculate_date_difference(erp["tx_date"], candidate["tx_date"])
            ref_equal = bool(erp["reference"] and candidate["reference"] and erp["reference"] == candidate["reference"])
            amount_equal = math.isclose(erp["amount"], candidate["amount"], abs_tol=0.01)
            passed = amount_equal and ref_equal and day_diff <= 1
            scored.append({
                "bank_tx_id": candidate["id"],
                "bank_external_id": candidate["external_id"],
                "amount_equal": amount_equal,
                "reference_equal": ref_equal,
                "day_diff": day_diff,
                "passed": passed
            })
            if passed:
                matches.append(candidate)
        return (matches[0], scored) if len(matches) == 1 else (None, scored)

    @staticmethod
    def perform_fuzzy_matching(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]]]:
        """Perform fuzzy matching between ERP and bank transactions."""
        scored, passed = [], []
        for candidate in candidates:
            similarity = DatabaseService.calculate_text_similarity(erp["description"], candidate["description"])
            amount_equal = math.isclose(erp["amount"], candidate["amount"], abs_tol=0.01)
            day_diff = DatabaseService.calculate_date_difference(erp["tx_date"], candidate["tx_date"])
            ok = amount_equal and similarity >= RECONCILIATION_THRESHOLDS.fuzzy_similarity and day_diff <= 2
            scored.append({
                "bank_tx_id": candidate["id"],
                "bank_external_id": candidate["external_id"],
                "similarity": similarity,
                "amount_equal": amount_equal,
                "day_diff": day_diff,
                "passed": ok
            })
            if ok:
                passed.append((candidate, similarity))
        return (passed[0][0], scored) if len(passed) == 1 else (None, scored)

    @staticmethod
    def extract_ml_features(erp: sqlite3.Row, bank: sqlite3.Row) -> List[float]:
        """Extract features for ML matching."""
        return [
            DatabaseService.calculate_amount_difference_ratio(erp["amount"], bank["amount"]),
            float(DatabaseService.calculate_date_difference(erp["tx_date"], bank["tx_date"])),
            DatabaseService.calculate_text_similarity(erp["description"], bank["description"]) / 100.0,
            1.0 if erp["reference"] and bank["reference"] and erp["reference"] == bank["reference"] else 0.0,
            1.0 if erp["account"] == bank["account"] else 0.0,
        ]

    @staticmethod
    def perform_ml_matching(erp: sqlite3.Row, candidates: List[sqlite3.Row]) -> Tuple[Optional[sqlite3.Row], List[Dict[str, Any]], float]:
        """Perform ML-based matching."""
        if not candidates or ML_MODEL_INSTANCE is None:
            return None, [], 0.0
        scores = []
        for candidate in candidates:
            features = TransactionMatcher.extract_ml_features(erp, candidate)
            probability = float(ML_MODEL_INSTANCE.predict_proba([features])[0][1])
            scores.append({
                "candidate": candidate,
                "probability": probability,
                "features": {
                    "amount_diff_ratio": round(features[0], 4),
                    "day_diff": int(features[1]),
                    "description_similarity": round(features[2] * 100, 2),
                    "reference_match": bool(features[3]),
                    "account_match": bool(features[4])
                }
            })
        scores.sort(key=lambda item: item["probability"], reverse=True)
        rendered = [{
            "bank_tx_id": item["candidate"]["id"],
            "bank_external_id": item["candidate"]["external_id"],
            "probability": round(item["probability"], 4),
            "features": item["features"]
        } for item in scores]
        top = scores[0]
        return top["candidate"], rendered, top["probability"]


class DecisionManager:
    """Handles reconciliation decisions."""

    @staticmethod
    def create_decision(conn: sqlite3.Connection, erp_row: sqlite3.Row, bank_row: Optional[sqlite3.Row],
                       stage: str, status: str, confidence: float, reasoning: str, human_required: bool) -> int:
        """Create a reconciliation decision."""
        ts = DatabaseService.get_current_timestamp()
        cur = conn.execute(
            "INSERT INTO decisions (erp_tx_id, bank_tx_id, stage, status, confidence, reasoning, human_required, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (erp_row["id"], bank_row["id"] if bank_row else None, stage, status, confidence, reasoning, 1 if human_required else 0, ts, ts),
        )
        decision_id = int(cur.lastrowid)
        conn.execute("UPDATE erp_transactions SET processed = 1 WHERE id = ?", (erp_row["id"],))
        if bank_row and status in {"auto_approved", "human_approved"}:
            conn.execute("UPDATE bank_transactions SET matched = 1 WHERE id = ?", (bank_row["id"],))
        return decision_id

    @staticmethod
    def export_lake_snapshot(conn: sqlite3.Connection) -> str:
        """Export current state to data lake."""
        snapshot = {
            "exported_at": DatabaseService.get_current_timestamp(),
            "app_version": APP_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "model_version": MODEL_VERSION,
            "decisions": [DatabaseService.convert_row_to_dict(row) for row in conn.execute("SELECT * FROM decisions ORDER BY id").fetchall()],
            "events": [{**DatabaseService.convert_row_to_dict(row), "payload_json": json.loads(row["payload_json"])} for row in conn.execute("SELECT * FROM events ORDER BY id").fetchall()]
        }
        output_path = LAKE_DIR / f"snapshot-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_path.relative_to(BASE_DIR))


class ReconciliationEngine:
    """Main reconciliation processing engine."""

    @staticmethod
    def execute_reconciliation_pipeline() -> Dict[str, Any]:
        """Execute the complete reconciliation pipeline."""
        with closing(DatabaseService.get_connection()) as conn:
            batch_id = datetime.utcnow().strftime("BATCH-%Y%m%d%H%M%S")
            EventLogger.log_event(conn, "batch_started", "batch", batch_id, {
                "app_version": APP_VERSION,
                "pipeline_version": PIPELINE_VERSION,
                "model_version": MODEL_VERSION,
                "thresholds": RECONCILIATION_THRESHOLDS.__dict__
            })

            unprocessed = TransactionMatcher.get_unprocessed_erp_transactions(conn)
            results = []

            for erp in unprocessed:
                entity_id = erp["external_id"]
                candidates = TransactionMatcher.get_candidate_bank_transactions(conn, erp)

                EventLogger.log_event(conn, "candidates_generated", "erp_transaction", entity_id, {
                    "erp_transaction": DatabaseService.convert_row_to_dict(erp),
                    "candidate_count": len(candidates),
                    "candidate_external_ids": [row["external_id"] for row in candidates]
                })

                # Exact matching
                exact_candidate, exact_scores = TransactionMatcher.perform_exact_matching(erp, candidates)
                EventLogger.log_event(conn, "exact_matching_evaluated", "erp_transaction", entity_id, {"scores": exact_scores})

                if exact_candidate is not None:
                    reason = "Match exato: valor e referência iguais, com diferença de data dentro da janela operacional."
                    decision_id = DecisionManager.create_decision(conn, erp, exact_candidate, "exact", "auto_approved", 0.99, reason, False)
                    EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                        "erp_external_id": erp["external_id"],
                        "bank_external_id": exact_candidate["external_id"],
                        "stage": "exact", "status": "auto_approved", "confidence": 0.99, "reasoning": reason
                    })
                    results.append({"erp": erp["external_id"], "stage": "exact", "status": "auto_approved"})
                    continue

                # Fuzzy matching
                fuzzy_candidate, fuzzy_scores = TransactionMatcher.perform_fuzzy_matching(erp, candidates)
                EventLogger.log_event(conn, "fuzzy_matching_evaluated", "erp_transaction", entity_id, {
                    "scores": fuzzy_scores, "similarity_threshold": RECONCILIATION_THRESHOLDS.fuzzy_similarity
                })

                if fuzzy_candidate is not None:
                    similarity = DatabaseService.calculate_text_similarity(erp["description"], fuzzy_candidate["description"])
                    if erp["amount"] >= RECONCILIATION_THRESHOLDS.materiality:
                        reason = "Candidato fuzzy forte, mas o valor ultrapassa o limiar de materialidade; a política exige revisão humana antes da aprovação."
                        decision_id = DecisionManager.create_decision(conn, erp, fuzzy_candidate, "fuzzy", "human_review", similarity / 100.0, reason, True)
                        EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                            "erp_external_id": erp["external_id"], "bank_external_id": fuzzy_candidate["external_id"],
                            "stage": "fuzzy", "status": "human_review", "confidence": round(similarity / 100.0, 4), "reason": "materiality_threshold"
                        })
                        results.append({"erp": erp["external_id"], "stage": "fuzzy", "status": "human_review"})
                        continue
                    reason = "Match fuzzy: valores iguais e histórico textual altamente semelhante dentro da janela de compensação."
                    decision_id = DecisionManager.create_decision(conn, erp, fuzzy_candidate, "fuzzy", "auto_approved", similarity / 100.0, reason, False)
                    EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                        "erp_external_id": erp["external_id"], "bank_external_id": fuzzy_candidate["external_id"],
                        "stage": "fuzzy", "status": "auto_approved", "confidence": round(similarity / 100.0, 4), "reasoning": reason
                    })
                    results.append({"erp": erp["external_id"], "stage": "fuzzy", "status": "auto_approved"})
                    continue

                # ML matching
                ml_candidate, ml_scores, ml_probability = TransactionMatcher.perform_ml_matching(erp, candidates)
                EventLogger.log_event(conn, "ml_matching_evaluated", "erp_transaction", entity_id, {
                    "scores": ml_scores, "thresholds": {
                        "auto_approve_ml": RECONCILIATION_THRESHOLDS.auto_approve_ml,
                        "review_ml": RECONCILIATION_THRESHOLDS.review_ml,
                        "materiality": RECONCILIATION_THRESHOLDS.materiality
                    }
                })

                if ml_candidate is not None and ml_probability >= RECONCILIATION_THRESHOLDS.auto_approve_ml and erp["amount"] < RECONCILIATION_THRESHOLDS.materiality:
                    reason = f"Match por ML: o modelo combinou proximidade de valor, datas, similaridade textual e conta. Probabilidade estimada: {ml_probability:.2%}."
                    decision_id = DecisionManager.create_decision(conn, erp, ml_candidate, "ml", "auto_approved", ml_probability, reason, False)
                    EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                        "erp_external_id": erp["external_id"], "bank_external_id": ml_candidate["external_id"],
                        "stage": "ml", "status": "auto_approved", "confidence": round(ml_probability, 4), "reasoning": reason
                    })
                    results.append({"erp": erp["external_id"], "stage": "ml", "status": "auto_approved"})
                    continue

                if ml_candidate is not None and ml_probability >= RECONCILIATION_THRESHOLDS.review_ml:
                    reason = "Candidato promissor, porém sem confiança suficiente para autoprovação ou sujeito a materialidade/ambiguidade. O caso segue para revisão humana com sugestão de vínculo."
                    decision_id = DecisionManager.create_decision(conn, erp, ml_candidate, "ml", "human_review", ml_probability, reason, True)
                    EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                        "erp_external_id": erp["external_id"], "bank_external_id": ml_candidate["external_id"],
                        "stage": "ml", "status": "human_review", "confidence": round(ml_probability, 4), "reasoning": reason
                    })
                    results.append({"erp": erp["external_id"], "stage": "ml", "status": "human_review"})
                    continue

                # Human review required
                reason = "Nenhuma regra ou score atingiu confiança suficiente; o caso foi direcionado para revisão humana."
                decision_id = DecisionManager.create_decision(conn, erp, None, "human", "human_review", max(ml_probability, 0.0), reason, True)
                EventLogger.log_event(conn, "decision_created", "decision", str(decision_id), {
                    "erp_external_id": erp["external_id"], "bank_external_id": None,
                    "stage": "human", "status": "human_review", "confidence": round(max(ml_probability, 0.0), 4), "reasoning": reason
                })
                results.append({"erp": erp["external_id"], "stage": "human", "status": "human_review"})

            lake_path = DecisionManager.export_lake_snapshot(conn)
            EventLogger.log_event(conn, "batch_finished", "batch", batch_id, {
                "processed_transactions": len(unprocessed), "result_summary": results, "lake_snapshot": lake_path
            })
            conn.commit()

        return {"batch_id": batch_id, "processed": len(results), "results": results, "lake_snapshot": lake_path}


class QualityAnalyzer:
    """Analyzes reconciliation quality metrics."""

    @staticmethod
    def get_decisions_with_transaction_context() -> List[Dict[str, Any]]:
        """Get decisions with full transaction context."""
        with closing(DatabaseService.get_connection()) as conn:
            rows = conn.execute(
                "SELECT d.*, e.external_id AS erp_external_id, e.amount AS erp_amount, e.description AS erp_description, e.expected_stage, e.expected_bank_external_id, b.external_id AS bank_external_id, b.description AS bank_description FROM decisions d JOIN erp_transactions e ON e.id = d.erp_tx_id LEFT JOIN bank_transactions b ON b.id = d.bank_tx_id ORDER BY d.id"
            ).fetchall()
            return [DatabaseService.convert_row_to_dict(row) for row in rows]

    @staticmethod
    def compute_quality_metrics() -> Dict[str, Any]:
        """Compute comprehensive quality metrics."""
        decisions = QualityAnalyzer.get_decisions_with_transaction_context()
        total = len(decisions)
        if total == 0:
            return {
                "total_decisions": 0,
                "precision": None,
                "recall": None,
                "f1": None,
                "human_queue_rate": None,
                "auto_approval_rate": None,
                "avg_confidence": None
            }

        auto_decisions = [d for d in decisions if d["status"] == "auto_approved"]
        human_queue = [d for d in decisions if d["status"] == "human_review"]

        true_positive = false_positive = false_negative = correct_stage = 0
        for d in decisions:
            expected_bank, got_bank = d["expected_bank_external_id"], d["bank_external_id"]
            expected_stage, got_stage = d["expected_stage"], d["stage"]
            if expected_stage == got_stage:
                correct_stage += 1
            if expected_bank:
                if got_bank == expected_bank:
                    true_positive += 1
                elif got_bank and got_bank != expected_bank:
                    false_positive += 1
                elif got_bank is None:
                    false_negative += 1
            elif got_bank is not None:
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
                "stage_accuracy_goal": ">= 0.80"
            }
        }

    @staticmethod
    def assess_system_degradation() -> Dict[str, Any]:
        """Assess if system performance has degraded."""
        quality = QualityAnalyzer.compute_quality_metrics()
        if quality["total_decisions"] == 0:
            return {"status": "unknown", "reason": "No decisions yet."}

        issues = []
        if quality["precision"] is not None and quality["precision"] < RECONCILIATION_THRESHOLDS.degradation_precision_floor:
            issues.append("precision_below_floor")
        if quality["human_queue_rate"] is not None and quality["human_queue_rate"] > RECONCILIATION_THRESHOLDS.degradation_human_queue_ceiling:
            issues.append("human_queue_above_ceiling")

        status = "healthy" if not issues else "degraded"
        return {
            "status": status,
            "issues": issues,
            "baseline": {
                "precision_floor": RECONCILIATION_THRESHOLDS.degradation_precision_floor,
                "human_queue_ceiling": RECONCILIATION_THRESHOLDS.degradation_human_queue_ceiling
            },
            "current": {
                "precision": quality.get("precision"),
                "human_queue_rate": quality.get("human_queue_rate")
            },
            "recommended_action": "Keep current autonomy." if status == "healthy" else "Reduce auto-approval, increase human sampling, and recalibrate thresholds."
        }


class EventQueryService:
    """Service for querying events."""

    @staticmethod
    def get_recent_events(limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from the database."""
        with closing(DatabaseService.get_connection()) as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{**DatabaseService.convert_row_to_dict(row), "payload_json": json.loads(row["payload_json"])} for row in rows]


class TransactionQueryService:
    """Service for querying transactions."""

    @staticmethod
    def get_all_transactions() -> Dict[str, Any]:
        """Get all ERP and bank transactions."""
        with closing(DatabaseService.get_connection()) as conn:
            erp = [DatabaseService.convert_row_to_dict(row) for row in conn.execute("SELECT * FROM erp_transactions ORDER BY id").fetchall()]
            bank = [DatabaseService.convert_row_to_dict(row) for row in conn.execute("SELECT * FROM bank_transactions ORDER BY id").fetchall()]
        return {"erp_transactions": erp, "bank_transactions": bank}

    @staticmethod
    def get_pending_human_reviews() -> List[Dict[str, Any]]:
        """Get transactions pending human review."""
        with closing(DatabaseService.get_connection()) as conn:
            rows = conn.execute(
                "SELECT d.*, e.external_id AS erp_external_id, e.description AS erp_description, b.external_id AS bank_external_id, b.description AS bank_description FROM decisions d JOIN erp_transactions e ON e.id = d.erp_tx_id LEFT JOIN bank_transactions b ON b.id = d.bank_tx_id WHERE d.status = 'human_review' ORDER BY d.id"
            ).fetchall()
        return [DatabaseService.convert_row_to_dict(row) for row in rows]


class ReviewService:
    """Service for handling human reviews."""

    @staticmethod
    def process_decision_review(decision_id: int, payload: ReviewDecisionPayload) -> Dict[str, Any]:
        """Process a human review decision."""
        if payload.action not in {"approve", "reject"}:
            raise HTTPException(status_code=400, detail="Action must be approve or reject.")

        with closing(DatabaseService.get_connection()) as conn:
            decision = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
            if not decision:
                raise HTTPException(status_code=404, detail="Decision not found.")
            if decision["status"] != "human_review":
                raise HTTPException(status_code=400, detail="Only pending decisions can be reviewed.")

            bank_tx_id = decision["bank_tx_id"]
            if payload.action == "approve" and payload.selected_bank_tx_id:
                bank_tx_id = payload.selected_bank_tx_id

            ts = DatabaseService.get_current_timestamp()
            status = "human_approved" if payload.action == "approve" else "human_rejected"
            reasoning = decision["reasoning"] + f" Human review: {payload.comment or 'no comment'}"

            conn.execute(
                "UPDATE decisions SET status = ?, bank_tx_id = ?, reasoning = ?, updated_at = ?, human_required = 0 WHERE id = ?",
                (status, bank_tx_id, reasoning, ts, decision_id)
            )

            if payload.action == "approve" and bank_tx_id:
                conn.execute("UPDATE bank_transactions SET matched = 1 WHERE id = ?", (bank_tx_id,))

            EventLogger.log_event(conn, "human_review_completed", "decision", str(decision_id), {
                "action": payload.action, "selected_bank_tx_id": bank_tx_id, "comment": payload.comment
            })
            conn.commit()

        return {"message": f"Decision {decision_id} updated with {status}."}

    @staticmethod
    def process_erp_review(payload: HumanReviewAction) -> Dict[str, Any]:
        """Process review by ERP transaction ID."""
        pending = TransactionQueryService.get_pending_human_reviews()
        target = next((item for item in pending if item["erp_external_id"] == payload.erp_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Case not found in human queue.")

        mapped_action = "approve" if payload.action in {"confirm_match", "approve"} else "reject"
        return ReviewService.process_decision_review(
            int(target["id"]),
            ReviewDecisionPayload(action=mapped_action, selected_bank_tx_id=payload.selected_bank_tx_id, comment=f"{payload.reviewer}: {payload.note}")
        )


# Module initialization
def initialize_scope1_module() -> None:
    """Initialize the scope 1 module."""
    global ML_MODEL_INSTANCE
    SchemaManager.create_database_schema()
    DataSeeder.seed_demo_data()
    if ML_MODEL_INSTANCE is None:
        ML_MODEL_INSTANCE = MLModelTrainer.train_model()


# API Endpoints
@router.post("/reset")
def reset_demo_data_endpoint() -> Dict[str, Any]:
    """Reset demo data."""
    DataSeeder.reset_demo_data()
    DataSeeder.seed_demo_data(force=True)
    return {"message": "Demo data reset successfully."}


@router.post("/run")
def execute_reconciliation_endpoint() -> Dict[str, Any]:
    """Execute reconciliation pipeline."""
    return ReconciliationEngine.execute_reconciliation_pipeline()


@router.get("/transactions")
def get_transactions_endpoint() -> Dict[str, Any]:
    """Get all transactions."""
    return TransactionQueryService.get_all_transactions()


@router.get("/dataset")
def get_dataset_endpoint() -> Dict[str, Any]:
    """Get transaction dataset."""
    return TransactionQueryService.get_all_transactions()


@router.get("/decisions")
def get_decisions_endpoint() -> Dict[str, Any]:
    """Get all decisions."""
    return {"decisions": QualityAnalyzer.get_decisions_with_transaction_context()}


@router.get("/events")
def get_events_endpoint(limit: int = 100) -> Dict[str, Any]:
    """Get recent events."""
    return {"events": EventQueryService.get_recent_events(limit)}


@router.get("/review/pending")
def get_pending_reviews_endpoint() -> Dict[str, Any]:
    """Get pending human reviews."""
    return {"pending_review": TransactionQueryService.get_pending_human_reviews()}


@router.get("/human-queue")
def get_human_queue_endpoint() -> Dict[str, Any]:
    """Get human review queue."""
    return {"cases": TransactionQueryService.get_pending_human_reviews()}


@router.post("/review/{decision_id}")
def review_decision_endpoint(decision_id: int, payload: ReviewDecisionPayload) -> Dict[str, Any]:
    """Review a specific decision."""
    return ReviewService.process_decision_review(decision_id, payload)


@router.post("/human-review")
def human_review_endpoint(payload: HumanReviewAction) -> Dict[str, Any]:
    """Process human review action."""
    return ReviewService.process_erp_review(payload)


@router.get("/quality")
def get_quality_metrics_endpoint() -> Dict[str, Any]:
    """Get quality metrics."""
    return QualityAnalyzer.compute_quality_metrics()


@router.get("/degradation")
def get_degradation_status_endpoint() -> Dict[str, Any]:
    """Get system degradation status."""
    return QualityAnalyzer.assess_system_degradation()


@router.get("/health")
def get_health_status_endpoint() -> Dict[str, Any]:
    """Get system health status."""
    return {
        "status": "ok",
        "app_version": APP_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "model_version": MODEL_VERSION,
        "database": str(DB_PATH)
    }
