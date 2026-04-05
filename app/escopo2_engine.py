from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from typing import Any

from .escopo2_data import closing_context, mock_current_batch, mock_history


class DetectorEngine:
    def __init__(self) -> None:
        self.history = mock_history()
        self.current_batch = mock_current_batch()
        self.context = closing_context()

    @staticmethod
    def _normalize_text(text: str) -> list[str]:
        text = (text or "").lower()
        for ch in [",", ".", "-", "/", "(", ")"]:
            text = text.replace(ch, " ")
        return [token for token in text.split() if len(token) > 2]

    def _duplicate_index(self) -> set[str]:
        counts = Counter((tx["account_code"], tx["amount"], tx["description"], tx["date"]) for tx in self.current_batch)
        dup_ids = set()
        for tx in self.current_batch:
            key = (tx["account_code"], tx["amount"], tx["description"], tx["date"])
            if counts[key] > 1:
                dup_ids.add(tx["id"])
        return dup_ids

    def _history_stats(self) -> dict[str, Any]:
        grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        history_tokens: dict[str, list[set[str]]] = defaultdict(list)
        for row in self.history:
            key = (row["account_code"], row["cost_center"], row["branch"])
            grouped[key].append(float(row["amount"]))
            history_tokens[row["account_code"]].append(set(self._normalize_text(row["description"])))
        stats_index: dict[tuple[str, str, str], dict[str, Any]] = {}
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
            stats_index[key] = {"mean": mean, "median": median, "std": std, "mad": mad, "q1": q1, "q3": q3, "iqr": iqr}
        stats_index["history_tokens"] = history_tokens
        return stats_index

    def _rule_layer(self, tx: dict[str, Any], duplicate_ids: set[str]) -> dict[str, Any]:
        findings = []
        if not tx["account_active"]:
            findings.append({"code": "CONTA_INATIVA", "message": "Conta contábil marcada como inativa.", "severity": 0.95, "confidence": 0.99, "critical": True})
        if tx["amount"] > tx["user_limit"]:
            findings.append({"code": "LIMITE_USUARIO", "message": "Valor acima do limite do usuário responsável.", "severity": 0.92, "confidence": 0.98, "critical": True})
        if tx["id"] in duplicate_ids:
            findings.append({"code": "POSSIVEL_DUPLICATA", "message": "Há lançamento duplicado no lote atual.", "severity": 0.80, "confidence": 0.90, "critical": False})
        if tx["date"] < str(self.context["current_close_start"]):
            findings.append({"code": "RETROATIVO", "message": "Lançamento com data anterior à janela corrente de fechamento.", "severity": 0.55, "confidence": 0.75, "critical": False})
        max_severity = max((f["severity"] for f in findings), default=0.0)
        max_confidence = max((f["confidence"] for f in findings), default=0.0)
        return {"findings": findings, "score": round((max_severity * 0.65) + (max_confidence * 0.35), 4) if findings else 0.0, "critical": any(f["critical"] for f in findings)}

    def _stat_layer(self, tx: dict[str, Any], stats_index: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
        key = (tx["account_code"], tx["cost_center"], tx["branch"])
        stats = stats_index.get(key)
        if not stats:
            return {"findings": [], "score": 0.10, "details": {"reason": "sem histórico"}}
        amount = float(tx["amount"])
        std = stats["std"]
        mean = stats["mean"]
        median = stats["median"]
        mad = stats["mad"]
        iqr = stats["iqr"]
        z_score = 0.0 if std == 0 else (amount - mean) / std
        robust_z = 0.0 if mad == 0 else 0.6745 * (amount - median) / mad
        upper_iqr = stats["q3"] + (1.5 * iqr)
        findings = []
        score = 0.0
        if abs(z_score) >= 2.5:
            findings.append(f"Z-score elevado ({z_score:.2f}).")
            score = max(score, min(1.0, abs(z_score) / 5.0))
        if abs(robust_z) >= 3.5:
            findings.append(f"Robust z-score elevado ({robust_z:.2f}).")
            score = max(score, min(1.0, abs(robust_z) / 6.0))
        if amount > upper_iqr and iqr > 0:
            findings.append(f"Acima do limite do IQR contextual (>{upper_iqr:.2f}).")
            score = max(score, 0.60)
        return {"findings": findings, "score": round(score, 4), "details": {"mean": round(mean, 2), "median": round(median, 2), "z_score": round(z_score, 2), "robust_z": round(robust_z, 2), "upper_iqr": round(upper_iqr, 2)}}

    def _semantic_layer(self, tx: dict[str, Any], stats_index: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
        history_tokens = stats_index["history_tokens"]
        current_tokens = set(self._normalize_text(tx["description"]))
        account_history = history_tokens.get(tx["account_code"], [])
        if not account_history:
            return {"findings": [], "score": 0.10, "details": {"reason": "sem histórico textual"}}
        similarities = []
        for token_set in account_history:
            union = current_tokens | token_set
            inter = current_tokens & token_set
            similarities.append(len(inter) / len(union) if union else 1.0)
        best_similarity = max(similarities) if similarities else 0.0
        findings = []
        score = 0.0
        if best_similarity < 0.25:
            findings.append("Descrição semanticamente distante do histórico esperado para a conta/categoria.")
            score = 0.78
        elif best_similarity < 0.45:
            findings.append("Descrição parcialmente compatível com o histórico, exigindo revisão contextual.")
            score = 0.48
        return {"findings": findings, "score": round(score, 4), "details": {"best_similarity": round(best_similarity, 3), "normalized_description": " ".join(sorted(current_tokens))}}

    @staticmethod
    def _materiality_score(amount: float) -> float:
        return round(min(1.0, amount / 100000.0), 4)

    def _structured_decision(self, tx: dict[str, Any], rule: dict[str, Any], stat: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
        anomaly_threshold = self.context["anomaly_threshold"]
        inconclusive_threshold = self.context["inconclusive_threshold"]
        materiality = self._materiality_score(float(tx["amount"]))
        if rule["critical"]:
            final_score = min(1.0, max(rule["score"], 0.82) + (0.15 * materiality))
        elif rule["score"] >= 0.65:
            final_score = min(1.0, max(0.72, rule["score"] + (0.10 * materiality)))
        elif semantic["score"] >= 0.75 and not rule["findings"] and stat["score"] < 0.60:
            final_score = max(inconclusive_threshold + 0.03, 0.50 + (0.10 * materiality))
        elif semantic["score"] >= 0.45 and stat["score"] >= 0.30 and not rule["findings"]:
            final_score = max(inconclusive_threshold + 0.01, 0.52 + (0.08 * materiality))
        else:
            final_score = (0.40 * rule["score"]) + (0.30 * stat["score"]) + (0.20 * semantic["score"]) + (0.10 * materiality)
        final_score = round(min(1.0, final_score), 4)
        if final_score >= anomaly_threshold:
            decision = "ANOMALIA"
        elif final_score >= inconclusive_threshold:
            decision = "INCONCLUSIVO"
        else:
            decision = "NORMAL"
        suggested_type = "NORMAL"
        if rule["findings"]:
            suggested_type = rule["findings"][0]["code"]
        elif stat["findings"]:
            suggested_type = "DESVIO_ESTATISTICO"
        elif semantic["findings"]:
            suggested_type = "DESVIO_SEMANTICO"
        return {"decision": decision, "final_score": final_score, "materiality": materiality, "suggested_type": suggested_type}

    def _explanation_layer(self, tx: dict[str, Any], rule: dict[str, Any], stat: dict[str, Any], semantic: dict[str, Any], structured: dict[str, Any]) -> dict[str, Any]:
        facts = []
        if rule["findings"]:
            facts.extend(f["message"] for f in rule["findings"])
        if stat["findings"]:
            facts.extend(stat["findings"])
        if semantic["findings"]:
            facts.extend(semantic["findings"])
        if not facts:
            facts.append("Não foram encontradas evidências suficientes para sustentar anomalia.")
        explanation = f"Lançamento {tx['id']} classificado como {structured['decision']} com score {structured['final_score']}. Conta {tx['account_code']} · valor R$ {tx['amount']:.2f}. Evidências: " + " ".join(facts)
        return {"explanation": explanation, "grounded_facts": facts, "guardrails": ["template_estruturado", "grounding_obrigatorio", "saida_inconclusiva"]}

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        duplicate_ids = self._duplicate_index()
        stats_index = self._history_stats()
        decisions = []
        audit_events = []
        for tx in self.current_batch:
            tx_started = time.perf_counter()
            rule = self._rule_layer(tx, duplicate_ids)
            stat = self._stat_layer(tx, stats_index)
            semantic = self._semantic_layer(tx, stats_index)
            structured = self._structured_decision(tx, rule, stat, semantic)
            explanation = self._explanation_layer(tx, rule, stat, semantic, structured)
            latency_ms = round((time.perf_counter() - tx_started) * 1000, 2)
            decision_payload = {"transaction": {k: v for k, v in tx.items() if k != "expected_label"}, "rule_layer": rule, "stat_layer": stat, "semantic_layer": semantic, "structured_decision": structured, "explanation_layer": explanation, "latency_ms": latency_ms}
            decisions.append(decision_payload)
            audit_events.append({"event_type": "AnomalyDecisionEvent", "transaction_id": tx["id"], "decision": structured["decision"], "final_score": structured["final_score"], "suggested_type": structured["suggested_type"], "grounded_facts": explanation["grounded_facts"], "expected_label": tx["expected_label"], "latency_ms": latency_ms})
        total = len(decisions)
        predicted_anomaly = [d for d in decisions if d["structured_decision"]["decision"] == "ANOMALIA"]
        expected_anomaly = [r for r in self.current_batch if r["expected_label"] == "ANOMALIA"]
        true_positives = sum(1 for d, tx in zip(decisions, self.current_batch) if d["structured_decision"]["decision"] == tx["expected_label"])
        anomaly_tp = sum(1 for d, tx in zip(decisions, self.current_batch) if d["structured_decision"]["decision"] == "ANOMALIA" and tx["expected_label"] == "ANOMALIA")
        false_positives = sum(1 for d, tx in zip(decisions, self.current_batch) if d["structured_decision"]["decision"] == "ANOMALIA" and tx["expected_label"] != "ANOMALIA")
        inconclusives = sum(1 for d in decisions if d["structured_decision"]["decision"] == "INCONCLUSIVO")
        operating_mode = {"mode": "ASSISTIDO" if inconclusives / total >= 0.30 else "NORMAL", "degradation_reasons": ["Aumento de casos inconclusivos nesta execução."] if inconclusives / total >= 0.30 else [], "fallback_actions": ["Bloquear automação para casos inconclusivos.", "Manter apenas regras críticas em modo totalmente automático."]}
        return {"summary": {"history_records": len(self.history), "current_records": len(self.current_batch), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}, "decisions": decisions, "audit_events": audit_events, "metrics": {"precision_at_k": round(anomaly_tp / max(1, len(predicted_anomaly)), 2), "recall": round(anomaly_tp / max(1, len(expected_anomaly)), 2), "false_positive_rate": round(false_positives / max(1, total), 2), "override_rate": round(inconclusives / total, 2), "inconclusive_rate": round(inconclusives / total, 2), "avg_latency_ms": round(sum(d["latency_ms"] for d in decisions) / total, 2), "agreement_with_mock": round(true_positives / total, 2)}, "operating_mode": operating_mode}
