from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class Transaction:
    id: str
    date: str
    account_code: str
    account_name: str
    account_active: bool
    cost_center: str
    branch: str
    counterparty: str
    description: str
    amount: float
    user: str
    user_limit: float
    expected_label: Optional[str] = None


# Historical transactions data
HISTORICAL_TRANSACTIONS_DATA = [
    Transaction(
        id="H001",
        date="2026-03-01",
        account_code="6.1.01",
        account_name="Despesas de Viagem",
        account_active=True,
        cost_center="ADM",
        branch="SP",
        counterparty="Agencia Delta",
        description="reembolso viagem hotel equipe comercial",
        amount=4200.0,
        user="ana",
        user_limit=15000.0,
    ),
    Transaction(
        id="H002",
        date="2026-03-07",
        account_code="6.1.01",
        account_name="Despesas de Viagem",
        account_active=True,
        cost_center="ADM",
        branch="SP",
        counterparty="Agencia Delta",
        description="reembolso viagem passagem time comercial",
        amount=5300.0,
        user="ana",
        user_limit=15000.0,
    ),
    Transaction(
        id="H003",
        date="2026-02-19",
        account_code="5.2.10",
        account_name="Serviços de TI",
        account_active=True,
        cost_center="TEC",
        branch="SP",
        counterparty="CloudNow",
        description="mensalidade plataforma cloud infraestrutura",
        amount=18500.0,
        user="bruno",
        user_limit=50000.0,
    ),
    Transaction(
        id="H004",
        date="2026-02-25",
        account_code="5.2.10",
        account_name="Serviços de TI",
        account_active=True,
        cost_center="TEC",
        branch="SP",
        counterparty="CloudNow",
        description="mensalidade cloud backup monitoramento",
        amount=19200.0,
        user="bruno",
        user_limit=50000.0,
    ),
    Transaction(
        id="H005",
        date="2026-02-28",
        account_code="4.1.02",
        account_name="Receita de Serviços",
        account_active=True,
        cost_center="FIN",
        branch="SP",
        counterparty="Cliente Atlas",
        description="receita contrato suporte mensal cliente atlas",
        amount=78000.0,
        user="carla",
        user_limit=150000.0,
    ),
    Transaction(
        id="H006",
        date="2026-03-05",
        account_code="6.9.90",
        account_name="Despesas Diversas",
        account_active=True,
        cost_center="ADM",
        branch="RJ",
        counterparty="Fornecedor Orion",
        description="compra material escritorio apoio administrativo",
        amount=1800.0,
        user="ana",
        user_limit=15000.0,
    ),
    Transaction(
        id="H007",
        date="2026-03-10",
        account_code="6.9.90",
        account_name="Despesas Diversas",
        account_active=True,
        cost_center="ADM",
        branch="RJ",
        counterparty="Fornecedor Orion",
        description="material escritorio impressora almoxarifado",
        amount=2100.0,
        user="ana",
        user_limit=15000.0,
    ),
    Transaction(
        id="H008",
        date="2026-02-11",
        account_code="5.3.40",
        account_name="Marketing",
        account_active=True,
        cost_center="MKT",
        branch="SP",
        counterparty="MediaHub",
        description="campanha digital leads topo funil",
        amount=32500.0,
        user="diego",
        user_limit=40000.0,
    ),
    Transaction(
        id="H009",
        date="2026-03-08",
        account_code="5.3.40",
        account_name="Marketing",
        account_active=True,
        cost_center="MKT",
        branch="SP",
        counterparty="MediaHub",
        description="campanha digital mídia performance",
        amount=34600.0,
        user="diego",
        user_limit=40000.0,
    ),
    Transaction(
        id="H010",
        date="2026-03-09",
        account_code="5.2.10",
        account_name="Serviços de TI",
        account_active=True,
        cost_center="TEC",
        branch="SP",
        counterparty="CloudNow",
        description="renovacao licencas cloud observabilidade",
        amount=20500.0,
        user="bruno",
        user_limit=50000.0,
    ),
]


# Current batch transactions data
CURRENT_BATCH_TRANSACTIONS_DATA = [
    Transaction(
        id="T001",
        date="2026-04-01",
        account_code="6.1.01",
        account_name="Despesas de Viagem",
        account_active=True,
        cost_center="ADM",
        branch="SP",
        counterparty="Agencia Delta",
        description="reembolso viagem hotel equipe comercial",
        amount=4600.0,
        user="ana",
        user_limit=15000.0,
        expected_label="NORMAL",
    ),
    Transaction(
        id="T002",
        date="2026-04-01",
        account_code="6.1.01",
        account_name="Despesas de Viagem",
        account_active=True,
        cost_center="ADM",
        branch="SP",
        counterparty="Agencia Delta",
        description="reembolso viagem hotel equipe comercial",
        amount=4600.0,
        user="ana",
        user_limit=15000.0,
        expected_label="ANOMALIA",
    ),
    Transaction(
        id="T003",
        date="2026-04-02",
        account_code="5.2.10",
        account_name="Serviços de TI",
        account_active=True,
        cost_center="TEC",
        branch="SP",
        counterparty="CloudNow",
        description="mensalidade plataforma cloud infraestrutura",
        amount=98000.0,
        user="bruno",
        user_limit=50000.0,
        expected_label="ANOMALIA",
    ),
    Transaction(
        id="T004",
        date="2026-04-02",
        account_code="9.9.99",
        account_name="Conta Inativa",
        account_active=False,
        cost_center="FIN",
        branch="SP",
        counterparty="Fornecedor Legacy",
        description="ajuste manual saldo fornecedor legado",
        amount=12500.0,
        user="carla",
        user_limit=150000.0,
        expected_label="ANOMALIA",
    ),
    Transaction(
        id="T005",
        date="2026-04-02",
        account_code="5.3.40",
        account_name="Marketing",
        account_active=True,
        cost_center="MKT",
        branch="SP",
        counterparty="MediaHub",
        description="campanha institucional tv aberta marca empregadora",
        amount=36800.0,
        user="diego",
        user_limit=40000.0,
        expected_label="INCONCLUSIVO",
    ),
    Transaction(
        id="T006",
        date="2026-03-10",
        account_code="6.9.90",
        account_name="Despesas Diversas",
        account_active=True,
        cost_center="ADM",
        branch="RJ",
        counterparty="Fornecedor Orion",
        description="compra material escritorio impressora",
        amount=1950.0,
        user="ana",
        user_limit=15000.0,
        expected_label="NORMAL",
    ),
]


# Closing configuration
CLOSING_CONFIGURATION = {
    "current_close_start": date(2026, 4, 4),
    "retroactive_cutoff_days": 25,
    "anomaly_threshold": 0.74,
    "inconclusive_threshold": 0.50,
}


class TransactionRepository:
    """Repository for transaction data following clean architecture principles."""

    @staticmethod
    def get_historical_transactions() -> List[Transaction]:
        """Retrieve historical transaction records."""
        return HISTORICAL_TRANSACTIONS_DATA.copy()

    @staticmethod
    def get_current_transaction_batch() -> List[Transaction]:
        """Retrieve current batch of transactions for processing."""
        return CURRENT_BATCH_TRANSACTIONS_DATA.copy()

    @staticmethod
    def get_closing_configuration() -> dict:
        """Retrieve closing period configuration settings."""
        return CLOSING_CONFIGURATION.copy()


# Backward compatibility functions
def mock_history() -> list[dict]:
    """Legacy function for historical transactions."""
    return [transaction.__dict__ for transaction in TransactionRepository.get_historical_transactions()]


def mock_current_batch() -> list[dict]:
    """Legacy function for current transaction batch."""
    return [transaction.__dict__ for transaction in TransactionRepository.get_current_transaction_batch()]


def closing_context() -> dict:
    """Legacy function for closing configuration."""
    return TransactionRepository.get_closing_configuration()
