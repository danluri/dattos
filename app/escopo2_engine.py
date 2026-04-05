from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .escopo2_data import closing_context, mock_current_batch, mock_history


@dataclass
class AnomalyThresholds:
    """Configuration thresholds for anomaly detection."""
    anomaly_threshold: float = 0.75
    inconclusive_threshold: float = 0.45
    duplicate_severity: float = 0.80
    inactive_account_severity: float = 0.95
    user_limit_severity: float = 0.92
    retroactive_severity: float = 0.55
    z_score_threshold: float = 2.5
    robust_z_threshold: float = 3.5
    iqr_multiplier: float = 1.5
    semantic_low_similarity: float = 0.25
    semantic_medium_similarity: float = 0.45
    materiality_base: float = 100000.0
    inconclusive_mode_threshold: float = 0.30


@dataclass
class TransactionAnalysis:
    """Result of transaction analysis."""
    transaction_id: str
    rule_layer: Dict[str, Any]
    stat_layer: Dict[str, Any]
    semantic_layer: Dict[str, Any]
    structured_decision: Dict[str, Any]
    explanation_layer: Dict[str, Any]
    latency_ms: float


@dataclass
class DetectionMetrics:
    """Performance metrics for anomaly detection."""
    precision_at_k: float
    recall: float
    false_positive_rate: float
    override_rate: float
    inconclusive_rate: float
    avg_latency_ms: float
    agreement_with_mock: float


class TextProcessor:
    """Handles text normalization and processing."""

    @staticmethod
    def normalize_text(text: str) -> List[str]:
        """Normalize text for analysis."""
        if not text:
            return []
        text = text.lower()
        for char in [",", ".", "-", "/", "(", ")"]:
            text = text.replace(char, " ")
        return [token for token in text.split() if len(token) > 2]


class DuplicateDetector:
    """Handles duplicate transaction detection."""

    @staticmethod
    def find_duplicates(transactions: List[Dict[str, Any]]) -> set[str]:
        """Identify duplicate transactions in the current batch."""
        counts = Counter(
            (tx["account_code"], tx["amount"], tx["description"], tx["date"])
            for tx in transactions
        )
        duplicate_ids = set()
        for tx in transactions:
            key = (tx["account_code"], tx["amount"], tx["description"], tx["date"])
            if counts[key] > 1:
                duplicate_ids.add(tx["id"])
        return duplicate_ids


class StatisticalAnalyzer:
    """Handles statistical analysis of transaction history."""

    @staticmethod
    def compute_history_statistics(history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute statistical measures for transaction history."""
        grouped: Dict[tuple[str, str, str], List[float]] = defaultdict(list)
        history_tokens: Dict[str, List[set[str]]] = defaultdict(list)

        for row in history:
            key = (row["account_code"], row["cost_center"], row["branch"])
            grouped[key].append(float(row["amount"]))
            history_tokens[row["account_code"]].append(
                set(TextProcessor.normalize_text(row["description"]))
            )

        stats_index: Dict[tuple[str, str, str], Dict[str, Any]] = {}

        for key, values in grouped.items():
            if len(values) == 1:
                mean = median = values[0]
                std = mad = iqr = 0.0
                q1 = q3 = values[0]
            else:
                mean = statistics.mean(values)
                median = statistics.median(values)
                std = statistics.pstdev(values)
                deviations = [abs(v - median) for v in values]
                mad = statistics.median(deviations)
                sorted_vals = sorted(values)
                q1 = sorted_vals[max(0, len(sorted_vals) // 4 - 1)]
                q3 = sorted_vals[min(len(sorted_vals) - 1, (3 * len(sorted_vals)) // 4)]
                iqr = q3 - q1

            stats_index[key] = {
                "mean": mean,
                "median": median,
                "std": std,
                "mad": mad,
                "q1": q1,
                "q3": q3,
                "iqr": iqr
            }

        stats_index["history_tokens"] = history_tokens
        return stats_index


class RuleBasedAnalyzer:
    """Handles rule-based anomaly detection."""

    def __init__(self, thresholds: AnomalyThresholds, context: Dict[str, Any]):
        self.thresholds = thresholds
        self.context = context

    def analyze_transaction(self, transaction: Dict[str, Any], duplicate_ids: set[str]) -> Dict[str, Any]:
        """Apply rule-based analysis to a transaction."""
        findings = []

        # Inactive account check
        if not transaction["account_active"]:
            findings.append({
                "code": "INACTIVE_ACCOUNT",
                "message": "Accounting account marked as inactive.",
                "severity": self.thresholds.inactive_account_severity,
                "confidence": 0.99,
                "critical": True
            })

        # User limit check
        if transaction["amount"] > transaction["user_limit"]:
            findings.append({
                "code": "USER_LIMIT_EXCEEDED",
                "message": "Amount exceeds responsible user's limit.",
                "severity": self.thresholds.user_limit_severity,
                "confidence": 0.98,
                "critical": True
            })

        # Duplicate check
        if transaction["id"] in duplicate_ids:
            findings.append({
                "code": "POSSIBLE_DUPLICATE",
                "message": "Duplicate entry found in current batch.",
                "severity": self.thresholds.duplicate_severity,
                "confidence": 0.90,
                "critical": False
            })

        # Retroactive check
        if transaction["date"] < str(self.context["current_close_start"]):
            findings.append({
                "code": "RETROACTIVE_ENTRY",
                "message": "Entry dated before current closing window.",
                "severity": self.thresholds.retroactive_severity,
                "confidence": 0.75,
                "critical": False
            })

        max_severity = max((f["severity"] for f in findings), default=0.0)
        max_confidence = max((f["confidence"] for f in findings), default=0.0)

        return {
            "findings": findings,
            "score": round((max_severity * 0.65) + (max_confidence * 0.35), 4) if findings else 0.0,
            "critical": any(f["critical"] for f in findings)
        }


class StatisticalDeviationAnalyzer:
    """Handles statistical deviation analysis."""

    def __init__(self, thresholds: AnomalyThresholds):
        self.thresholds = thresholds

    def analyze_transaction(self, transaction: Dict[str, Any], stats_index: Dict[str, Any]) -> Dict[str, Any]:
        """Apply statistical analysis to detect deviations."""
        key = (transaction["account_code"], transaction["cost_center"], transaction["branch"])
        stats = stats_index.get(key)

        if not stats:
            return {
                "findings": [],
                "score": 0.10,
                "details": {"reason": "no_history_available"}
            }

        amount = float(transaction["amount"])
        std = stats["std"]
        mean = stats["mean"]
        median = stats["median"]
        mad = stats["mad"]
        iqr = stats["iqr"]

        z_score = 0.0 if std == 0 else (amount - mean) / std
        robust_z = 0.0 if mad == 0 else 0.6745 * (amount - median) / mad
        upper_iqr = stats["q3"] + (self.thresholds.iqr_multiplier * iqr)

        findings = []
        score = 0.0

        if abs(z_score) >= self.thresholds.z_score_threshold:
            findings.append(f"High z-score ({z_score:.2f}).")
            score = max(score, min(1.0, abs(z_score) / 5.0))

        if abs(robust_z) >= self.thresholds.robust_z_threshold:
            findings.append(f"High robust z-score ({robust_z:.2f}).")
            score = max(score, min(1.0, abs(robust_z) / 6.0))

        if amount > upper_iqr and iqr > 0:
            findings.append(f"Above contextual IQR limit (>{upper_iqr:.2f}).")
            score = max(score, 0.60)

        return {
            "findings": findings,
            "score": round(score, 4),
            "details": {
                "mean": round(mean, 2),
                "median": round(median, 2),
                "z_score": round(z_score, 2),
                "robust_z": round(robust_z, 2),
                "upper_iqr": round(upper_iqr, 2)
            }
        }


class SemanticAnalyzer:
    """Handles semantic analysis of transaction descriptions."""

    def __init__(self, thresholds: AnomalyThresholds):
        self.thresholds = thresholds

    def analyze_transaction(self, transaction: Dict[str, Any], stats_index: Dict[str, Any]) -> Dict[str, Any]:
        """Apply semantic analysis to transaction description."""
        history_tokens = stats_index.get("history_tokens", {})
        current_tokens = set(TextProcessor.normalize_text(transaction["description"]))

        account_history = history_tokens.get(transaction["account_code"], [])
        if not account_history:
            return {
                "findings": [],
                "score": 0.10,
                "details": {"reason": "no_textual_history"}
            }

        similarities = []
        for token_set in account_history:
            union = current_tokens | token_set
            intersection = current_tokens & token_set
            similarity = len(intersection) / len(union) if union else 1.0
            similarities.append(similarity)

        best_similarity = max(similarities) if similarities else 0.0
        findings = []
        score = 0.0

        if best_similarity < self.thresholds.semantic_low_similarity:
            findings.append("Description semantically distant from expected account history.")
            score = 0.78
        elif best_similarity < self.thresholds.semantic_medium_similarity:
            findings.append("Description partially compatible with history, requires contextual review.")
            score = 0.48

        return {
            "findings": findings,
            "score": round(score, 4),
            "details": {
                "best_similarity": round(best_similarity, 3),
                "normalized_description": " ".join(sorted(current_tokens))
            }
        }


class DecisionEngine:
    """Handles structured decision making."""

    def __init__(self, thresholds: AnomalyThresholds):
        self.thresholds = thresholds

    def calculate_materiality_score(self, amount: float) -> float:
        """Calculate materiality score based on transaction amount."""
        return round(min(1.0, amount / self.thresholds.materiality_base), 4)

    def make_structured_decision(self, transaction: Dict[str, Any], rule_result: Dict[str, Any],
                               stat_result: Dict[str, Any], semantic_result: Dict[str, Any]) -> Dict[str, Any]:
        """Make final structured decision based on all analysis layers."""
        materiality = self.calculate_materiality_score(float(transaction["amount"]))

        if rule_result["critical"]:
            final_score = min(1.0, max(rule_result["score"], 0.82) + (0.15 * materiality))
        elif rule_result["score"] >= 0.65:
            final_score = min(1.0, max(0.72, rule_result["score"] + (0.10 * materiality)))
        elif semantic_result["score"] >= 0.75 and not rule_result["findings"] and stat_result["score"] < 0.60:
            final_score = max(self.thresholds.inconclusive_threshold + 0.03, 0.50 + (0.10 * materiality))
        elif semantic_result["score"] >= 0.45 and stat_result["score"] >= 0.30 and not rule_result["findings"]:
            final_score = max(self.thresholds.inconclusive_threshold + 0.01, 0.52 + (0.08 * materiality))
        else:
            final_score = (0.40 * rule_result["score"]) + (0.30 * stat_result["score"]) + \
                         (0.20 * semantic_result["score"]) + (0.10 * materiality)

        final_score = round(min(1.0, final_score), 4)

        if final_score >= self.thresholds.anomaly_threshold:
            decision = "ANOMALY"
        elif final_score >= self.thresholds.inconclusive_threshold:
            decision = "INCONCLUSIVE"
        else:
            decision = "NORMAL"

        suggested_type = "NORMAL"
        if rule_result["findings"]:
            suggested_type = rule_result["findings"][0]["code"]
        elif stat_result["findings"]:
            suggested_type = "STATISTICAL_DEVIATION"
        elif semantic_result["findings"]:
            suggested_type = "SEMANTIC_DEVIATION"

        return {
            "decision": decision,
            "final_score": final_score,
            "materiality": materiality,
            "suggested_type": suggested_type
        }


class ExplanationGenerator:
    """Generates explanations for decisions."""

    @staticmethod
    def generate_explanation(transaction: Dict[str, Any], rule_result: Dict[str, Any],
                           stat_result: Dict[str, Any], semantic_result: Dict[str, Any],
                           decision_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive explanation for the decision."""
        facts = []

        if rule_result["findings"]:
            facts.extend(f["message"] for f in rule_result["findings"])
        if stat_result["findings"]:
            facts.extend(stat_result["findings"])
        if semantic_result["findings"]:
            facts.extend(semantic_result["findings"])

        if not facts:
            facts.append("No sufficient evidence found to support anomaly.")

        explanation = (
            f"Transaction {transaction['id']} classified as {decision_result['decision']} "
            f"with score {decision_result['final_score']}. Account {transaction['account_code']} · "
            f"amount R$ {transaction['amount']:.2f}. Evidence: {' '.join(facts)}"
        )

        return {
            "explanation": explanation,
            "grounded_facts": facts,
            "guardrails": ["structured_template", "mandatory_grounding", "inconclusive_output"]
        }


class MetricsCalculator:
    """Calculates performance metrics."""

    @staticmethod
    def calculate_metrics(decisions: List[TransactionAnalysis], transactions: List[Dict[str, Any]]) -> DetectionMetrics:
        """Calculate comprehensive performance metrics."""
        total = len(decisions)
        if total == 0:
            return DetectionMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        predicted_anomalies = [d for d in decisions if d.structured_decision["decision"] == "ANOMALY"]
        expected_anomalies = [tx for tx in transactions if tx["expected_label"] == "ANOMALY"]

        true_positives = sum(
            1 for d, tx in zip(decisions, transactions)
            if d.structured_decision["decision"] == tx["expected_label"]
        )

        anomaly_tp = sum(
            1 for d, tx in zip(decisions, transactions)
            if d.structured_decision["decision"] == "ANOMALY" and tx["expected_label"] == "ANOMALY"
        )

        false_positives = sum(
            1 for d, tx in zip(decisions, transactions)
            if d.structured_decision["decision"] == "ANOMALY" and tx["expected_label"] != "ANOMALY"
        )

        inconclusives = sum(
            1 for d in decisions
            if d.structured_decision["decision"] == "INCONCLUSIVE"
        )

        return DetectionMetrics(
            precision_at_k=round(anomaly_tp / max(1, len(predicted_anomalies)), 2),
            recall=round(anomaly_tp / max(1, len(expected_anomalies)), 2),
            false_positive_rate=round(false_positives / max(1, total), 2),
            override_rate=round(inconclusives / total, 2),
            inconclusive_rate=round(inconclusives / total, 2),
            avg_latency_ms=round(sum(d.latency_ms for d in decisions) / total, 2),
            agreement_with_mock=round(true_positives / total, 2)
        )


class OperatingModeAnalyzer:
    """Analyzes operating mode based on performance."""

    @staticmethod
    def determine_operating_mode(metrics: DetectionMetrics, thresholds: AnomalyThresholds) -> Dict[str, Any]:
        """Determine appropriate operating mode."""
        is_degraded = metrics.inconclusive_rate >= thresholds.inconclusive_mode_threshold

        mode = "ASSISTED" if is_degraded else "NORMAL"
        degradation_reasons = (
            ["Increased inconclusive cases in this execution."]
            if is_degraded else []
        )
        fallback_actions = (
            ["Block automation for inconclusive cases.", "Maintain only critical rules in fully automatic mode."]
            if is_degraded else []
        )

        return {
            "mode": mode,
            "degradation_reasons": degradation_reasons,
            "fallback_actions": fallback_actions
        }


class AnomalyDetectionEngine:
    """Main anomaly detection engine coordinating all analysis layers."""

    def __init__(self) -> None:
        self.history = mock_history()
        self.current_batch = mock_current_batch()
        self.context = closing_context()
        self.thresholds = AnomalyThresholds(
            anomaly_threshold=self.context["anomaly_threshold"],
            inconclusive_threshold=self.context["inconclusive_threshold"]
        )

        # Initialize analyzers
        self.rule_analyzer = RuleBasedAnalyzer(self.thresholds, self.context)
        self.stat_analyzer = StatisticalDeviationAnalyzer(self.thresholds)
        self.semantic_analyzer = SemanticAnalyzer(self.thresholds)
        self.decision_engine = DecisionEngine(self.thresholds)

    def run_detection(self) -> Dict[str, Any]:
        """Execute complete anomaly detection pipeline."""
        start_time = time.perf_counter()

        # Preprocessing
        duplicate_ids = DuplicateDetector.find_duplicates(self.current_batch)
        stats_index = StatisticalAnalyzer.compute_history_statistics(self.history)

        # Process each transaction
        analyses = []
        audit_events = []

        for transaction in self.current_batch:
            tx_start_time = time.perf_counter()

            # Apply analysis layers
            rule_result = self.rule_analyzer.analyze_transaction(transaction, duplicate_ids)
            stat_result = self.stat_analyzer.analyze_transaction(transaction, stats_index)
            semantic_result = self.semantic_analyzer.analyze_transaction(transaction, stats_index)
            decision_result = self.decision_engine.make_structured_decision(
                transaction, rule_result, stat_result, semantic_result
            )
            explanation_result = ExplanationGenerator.generate_explanation(
                transaction, rule_result, stat_result, semantic_result, decision_result
            )

            latency_ms = round((time.perf_counter() - tx_start_time) * 1000, 2)

            # Create analysis result
            analysis = TransactionAnalysis(
                transaction_id=transaction["id"],
                rule_layer=rule_result,
                stat_layer=stat_result,
                semantic_layer=semantic_result,
                structured_decision=decision_result,
                explanation_layer=explanation_result,
                latency_ms=latency_ms
            )
            analyses.append(analysis)

            # Create audit event
            audit_events.append({
                "event_type": "AnomalyDecisionEvent",
                "transaction_id": transaction["id"],
                "decision": decision_result["decision"],
                "final_score": decision_result["final_score"],
                "suggested_type": decision_result["suggested_type"],
                "grounded_facts": explanation_result["grounded_facts"],
                "expected_label": transaction["expected_label"],
                "latency_ms": latency_ms
            })

        # Calculate metrics and operating mode
        metrics = MetricsCalculator.calculate_metrics(analyses, self.current_batch)
        operating_mode = OperatingModeAnalyzer.determine_operating_mode(metrics, self.thresholds)

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Convert analyses to dictionaries for output
        decisions = []
        for analysis in analyses:
            decision_dict = {
                "transaction": {k: v for k, v in next(tx for tx in self.current_batch if tx["id"] == analysis.transaction_id).items() if k != "expected_label"},
                "rule_layer": analysis.rule_layer,
                "stat_layer": analysis.stat_layer,
                "semantic_layer": analysis.semantic_layer,
                "structured_decision": analysis.structured_decision,
                "explanation_layer": analysis.explanation_layer,
                "latency_ms": analysis.latency_ms
            }
            decisions.append(decision_dict)

        return {
            "summary": {
                "history_records": len(self.history),
                "current_records": len(self.current_batch),
                "elapsed_ms": total_elapsed_ms
            },
            "decisions": decisions,
            "audit_events": audit_events,
            "metrics": {
                "precision_at_k": metrics.precision_at_k,
                "recall": metrics.recall,
                "false_positive_rate": metrics.false_positive_rate,
                "override_rate": metrics.override_rate,
                "inconclusive_rate": metrics.inconclusive_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
                "agreement_with_mock": metrics.agreement_with_mock
            },
            "operating_mode": operating_mode
        }


# Backward compatibility function
def run_anomaly_detection() -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    engine = AnomalyDetectionEngine()
    return engine.run_detection()
